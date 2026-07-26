"""
Plan-and-Solve Agent 实现。

这是一种更适合复杂查询的 Agent 模式：
1. 先为 SQL 查询创建结构化计划
2. 再逐步执行计划中的步骤
3. 根据执行反馈细化计划或 SQL

该模式更适合需要多步推理的复杂查询，
例如多表 JOIN、嵌套子查询或聚合查询。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from overrides import override

from sql_agent.agent.base import AgentResult, SQLAgent, StepResult
from sql_agent.agent.tools import AgentToolkit
from sql_agent.core.types import (
     Conversation,
     DatabaseConnection,
     LLMConfig,
     Prompt,
     SQLStatus,
     TableDescription,
)

logger = logging.getLogger(__name__)


PLAN_SYSTEM_PROMPT = """You are a SQL expert assistant. For complex questions, you plan first and then execute.

PHASE 1 - PLAN: Analyze the question and create a structured plan:
1. Identify required tables and JOIN paths
2. Identify required columns and aggregations
3. Identify filters, grouping, and sorting
4. Write the SQL step-by-step

PHASE 2 - EXECUTE: Carry out the plan using available tools.

Available tools:
{tool_descriptions}

{few_shot_prompt}
{instructions_prompt}
"""

PLAN_PROMPT = """Create a detailed SQL generation plan for this question:

Question: {question}
Database tables available: {table_list}
{conversation_context}

Output your plan in this format:
Plan:
1. [Step 1 description]
2. [Step 2 description]
...

Tables needed: [list of tables]
JOIN conditions: [how tables relate]
Filters: [WHERE conditions]
Aggregations: [GROUP BY, HAVING]
Order: [ORDER BY]

After creating the plan, begin executing it using the available tools.
First, verify the schema of relevant tables.
"""

FINAL_SQL_PROMPT = """Based on the plan and all gathered information, write the final SQL query.

Question: {question}
Plan: {plan_text}
{conversation_context}

Output the complete SQL query inside a ```sql block.
"""


class PlanSolveAgent(SQLAgent):
     """
     Plan-and-Solve Agent。

     将推理拆成两个阶段：
     1. 规划：分析问题并组织求解路径
     2. 求解：逐步执行计划

     更适合复杂的多表查询。
     """

     def __init__(self, system, llm_config=None, agent_config=None):
         super().__init__(system, llm_config, agent_config)

     def _build_system_prompt(self, toolkit: AgentToolkit) -> str:
         tools = toolkit.get_tools()
         tool_descs = "\n".join(f"- {t.name}: {t.description}" for t in tools)

         few_shot_prompt = ""
         if toolkit.few_shot_examples:
             few_shot_prompt = "\nFew-shot examples are available via FewshotExamplesRetriever tool."
         instructions_prompt = ""
         if toolkit.instructions:
             instructions_prompt = "\nAdmin instructions are available via GetAdminInstructions tool."

         return PLAN_SYSTEM_PROMPT.format(
             tool_descriptions=tool_descs,
             few_shot_prompt=few_shot_prompt,
             instructions_prompt=instructions_prompt,
         )

     @override
     def generate_sql(
         self,
         prompt: Prompt,
         database_connection: DatabaseConnection,
         table_descriptions: List[TableDescription],
         conversation: Optional[Conversation] = None,
         few_shot_examples: Optional[List[Dict[str, Any]]] = None,
         instructions: Optional[List[Dict[str, str]]] = None,
         metadata: Optional[Dict[str, Any]] = None,
     ) -> AgentResult:
         from sql_agent.llm.base import LLMBackend
         from sql_agent.sql.database import SQLDatabase

         llm = self.system.instance(LLMBackend)
         database = SQLDatabase.get_sql_engine(database_connection)

         toolkit = AgentToolkit(
             database=database,
             db_scan=table_descriptions,
             llm_backend=llm,
             few_shot_examples=few_shot_examples,
             instructions=instructions,
             is_multiple_schema=bool(prompt.schemas),
         )

         system_prompt = self._build_system_prompt(toolkit)
         tools_by_name = {t.name: t for t in toolkit.get_tools()}
         steps = []
         total_tokens = 0

         # 对话上下文
         conv_context = ""
         if conversation and len(conversation.turns) >= 2:
             conv_context = "Conversation history:\n"
             for turn in conversation.turns[-4:]:
                 conv_context += f"{'User' if turn.role == 'user' else 'Assistant'}: {turn.content}\n"
                 if turn.sql:
                     conv_context += f"SQL: {turn.sql}\n"

         # ─── 阶段 1：创建计划 ──────────────────────────────
         table_list = ", ".join(
             f"{t.schema_name}.{t.table_name}" if t.schema_name else t.table_name
             for t in table_descriptions[:10]
         )
         plan_messages = [
             {"role": "system", "content": system_prompt},
             {"role": "user", "content": PLAN_PROMPT.format(
                 question=prompt.text,
                 table_list=table_list,
                 conversation_context=conv_context,
             )}
         ]

         plan_response = llm.generate(plan_messages, config=self.llm_config)
         total_tokens += llm.count_tokens(plan_response)
         plan_text = plan_response.strip()
         logger.info(f"Plan-Solve Agent plan:\n{plan_text[:500]}")

         steps.append(StepResult(
             thought="Created SQL generation plan",
             action="Plan",
             action_input=plan_text,
             observation="Plan created successfully"
         ))

         # ─── 阶段 2：执行计划 ──────────────────────────────
         messages = [
             {"role": "system", "content": system_prompt},
             {"role": "user", "content": f"Plan: {plan_text}\n\nQuestion: {prompt.text}\n{conv_context}\nExecute the plan using available tools."}
         ]

         max_iter = self.agent_config.max_iterations
         start_time = time.time()

         for iteration in range(max_iter):
             elapsed = time.time() - start_time
             if elapsed > self.agent_config.max_execution_time:
                 logger.warning(f"Plan-Solve timed out after {elapsed:.1f}s")
                 break

             response = llm.generate(messages, config=self.llm_config)
             total_tokens += llm.count_tokens(response)

             # 检查是否已经生成最终 SQL
             if "```sql" in response:
                 sql = self.extract_sql_from_output(response)
                 if sql:
                     logger.info(f"Plan-Solve Agent generated SQL: {sql[:100]}...")
                     return AgentResult(
                         sql=sql,
                         status=SQLStatus.PENDING,
                         steps=steps,
                         tokens_used=total_tokens,
                     )

             # 解析工具调用
             action_match = re.search(r"Action:\s*(\w+)", response)
             if not action_match:
                 messages.append({"role": "assistant", "content": response})
                 messages.append({
                     "role": "user",
                     "content": f"Continue with the plan. Use tools or output the final SQL in a ```sql block."
                 })
                 continue

             tool_name = action_match.group(1)
             input_match = re.search(r"Action Input:\s*(.*?)(?=Thought:|Action:|$)", response, re.DOTALL)
             tool_input = input_match.group(1).strip() if input_match else ""

             if tool_name not in tools_by_name:
                 obs = f"Unknown tool: {tool_name}"
             else:
                 try:
                     result = tools_by_name[tool_name].fn(tool_input)
                     obs = result.output
                 except Exception as e:
                     obs = f"Error: {str(e)}"

             obs = self.truncate_observation(obs)

             thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", response, re.DOTALL)
             steps.append(StepResult(
                 thought=thought_match.group(1).strip() if thought_match else "",
                 action=tool_name,
                 action_input=tool_input,
                 observation=obs,
             ))

             messages.append({"role": "assistant", "content": response})
             messages.append({"role": "user", "content": f"Observation: {obs}\n\nContinue with the plan."})

         # 降级方案：不再执行工具，直接生成最终 SQL
         logger.warning("Plan-Solve reached max iterations, generating final SQL")
         final_prompt = FINAL_SQL_PROMPT.format(
             question=prompt.text,
             plan_text=plan_text,
             conversation_context=conv_context,
         )
         messages.append({"role": "user", "content": final_prompt})
         final_response = llm.generate(messages, config=self.llm_config)
         sql = self.extract_sql_from_output(final_response)

         if sql:
             return AgentResult(sql=sql, status=SQLStatus.PENDING, steps=steps, tokens_used=total_tokens)
         return AgentResult(error="Plan-and-Solve failed to generate SQL", status=SQLStatus.INVALID, steps=steps, tokens_used=total_tokens)

     @override
     def stream_sql(
         self,
         prompt: Prompt,
         database_connection: DatabaseConnection,
         table_descriptions: List[TableDescription],
         conversation: Optional[Conversation] = None,
         few_shot_examples: Optional[List[Dict[str, Any]]] = None,
         instructions: Optional[List[Dict[str, str]]] = None,
         metadata: Optional[Dict[str, Any]] = None,
     ):
         yield {"type": "info", "content": "Streaming not yet implemented for PlanSolveAgent"}
         result = self.generate_sql(
             prompt=prompt,
             database_connection=database_connection,
             table_descriptions=table_descriptions,
             conversation=conversation,
             few_shot_examples=few_shot_examples,
             instructions=instructions,
             metadata=metadata,
         )
         yield {"type": "result", "content": result}
