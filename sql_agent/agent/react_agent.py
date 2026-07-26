"""
ReAct Agent 实现。

使用原生 ReAct 模式替代 Dataherald 中的 LangChain ZeroShotAgent。
关键改进：
- 更可控的 Thought-Action-Observation 循环
- 更清晰的错误处理和重试逻辑
- 不与 LangChain 耦合，职责边界更清晰
- 集成 token 统计
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
    AgentConfig,
    Conversation,
    DatabaseConnection,
    LLMConfig,
    Prompt,
    SQLStatus,
    TableDescription,
)

logger = logging.getLogger(__name__)


REACT_SYSTEM_PROMPT = """You are a SQL expert assistant. Your task is to convert natural language questions into accurate SQL queries.

You operate by iteratively using tools, following this loop:
Thought: Analyze the current state and decide what to do next
Action: The name of the tool to use
Action Input: The input to the tool
Observation: The result of the tool

After enough observations, output the final SQL query in a ```sql block.

Available tools:
{tool_descriptions}

Follow these rules:
1. Always start by understanding which tables are relevant using DbTablesWithRelevanceScores
2. Get the schema of relevant tables using DbRelevantTablesSchema
3. Check column values if the question mentions specific entities
4. Use few-shot examples if available to guide your SQL style
5. Always verify your SQL by executing it with SqlDbQuery before finalizing
6. If you get an error, analyze it and fix your query
7. For date/time queries, always use SystemTime first
8. Follow any admin instructions exactly
9. Use proper JOIN conditions based on foreign keys
{few_shot_prompt}
{instructions_prompt}
"""

FINAL_PROMPT = """Based on all the information gathered, generate the final SQL query.
{conversation_context}
Question: {question}

Output the SQL query inside a ```sql block.
Also explain your reasoning briefly before the SQL block.
"""


class ReActAgent(SQLAgent):
    """
    ReAct（Reasoning + Acting）SQL Agent。

    原生实现 Thought-Action-Observation 循环，
    不依赖 LangChain 的 ZeroShotAgent。
    """

    def __init__(
        self,
        system,
        llm_config: Optional[LLMConfig] = None,
        agent_config: Optional[AgentConfig] = None,
    ):
        super().__init__(system, llm_config, agent_config)
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = self.system.instance("sql_agent.llm.base.LLMBackend")
        return self._llm

    def _build_tool_descriptions(self, tools) -> str:
        """为系统提示词构造工具描述"""
        descs = []
        for tool in tools:
            descs.append(f"- {tool.name}: {tool.description}")
        return "\n".join(descs)

    def _parse_react_step(self, text: str) -> Optional[Dict[str, str]]:
        """从 LLM 输出中解析 ReAct 步骤"""
        thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", text, re.DOTALL)
        action_match = re.search(r"Action:\s*(\w+)", text)
        input_match = re.search(r"Action Input:\s*(.*?)(?=Thought:|$)", text, re.DOTALL)

        if action_match:
            step = {}
            if thought_match:
                step["thought"] = thought_match.group(1).strip()
            step["action"] = action_match.group(1)
            step["action_input"] = input_match.group(1).strip() if input_match else ""
            return step
        return None

    def _build_system_prompt(self, toolkit: AgentToolkit) -> str:
        """构造包含工具描述的系统提示词"""
        tools = toolkit.get_tools()
        tool_descs = self._build_tool_descriptions(tools)

        few_shot_prompt = ""
        if toolkit.few_shot_examples:
            few_shot_prompt = "\nFew-shot examples are available via FewshotExamplesRetriever tool."

        instructions_prompt = ""
        if toolkit.instructions:
            instructions_prompt = (
                "\nAdmin instructions are available via GetAdminInstructions tool."
            )

        return REACT_SYSTEM_PROMPT.format(
            tool_descriptions=tool_descs,
            few_shot_prompt=few_shot_prompt,
            instructions_prompt=instructions_prompt,
        )

    def _build_conversation_context(self, conversation: Optional[Conversation]) -> str:
        """构造多轮对话历史上下文"""
        if not conversation or len(conversation.turns) < 2:
            return ""

        context = "\nConversation history:\n"
        for turn in conversation.turns[-4:]:  # 最近 4 轮
            role = "User" if turn.role == "user" else "Assistant"
            context += f"{role}: {turn.content}\n"
            if turn.sql:
                context += f"SQL: {turn.sql}\n"
                if turn.sql_result:
                    context += f"Result: {turn.sql_result[:200]}\n"
        return context + "\n"

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

        messages = [{"role": "system", "content": system_prompt}]
        conversation_context = self._build_conversation_context(conversation)

        # 初始用户消息
        user_msg = (
            f"Question: {prompt.text}\n\n{conversation_context}"
            if conversation_context
            else f"Question: {prompt.text}"
        )
        messages.append({"role": "user", "content": user_msg})

        steps = []
        total_tokens = 0
        max_iter = self.agent_config.max_iterations
        start_time = time.time()

        for iteration in range(max_iter):
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed > self.agent_config.max_execution_time:
                logger.warning(f"Agent timed out after {elapsed:.1f}s")
                break

            # 获取 LLM 响应
            response = llm.generate(
                messages=messages,
                config=self.llm_config,
            )
            total_tokens += llm.count_tokens(response)

            # 检查是否已经给出最终答案（包含 SQL 代码块）
            if "```sql" in response:
                sql = self.extract_sql_from_output(response)
                if sql:
                    logger.info(f"Agent generated SQL: {sql[:100]}...")
                    return AgentResult(
                        sql=sql,
                        status=SQLStatus.PENDING,
                        steps=steps,
                        tokens_used=total_tokens,
                    )

            # 解析 ReAct 步骤
            step_data = self._parse_react_step(response)
            if not step_data:
                logger.warning(f"Could not parse step from response: {response[:200]}")
                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": "Please format your response with Thought/Action/Action Input sections.",
                    }
                )
                continue

            # 执行工具
            tool_name = step_data["action"]
            tool_input = step_data.get("action_input", "")

            if tool_name not in tools_by_name:
                obs = f"Error: Unknown tool '{tool_name}'. Available tools: {', '.join(tools_by_name.keys())}"
                logger.warning(obs)
            else:
                try:
                    tool_result = tools_by_name[tool_name].fn(tool_input)
                    obs = tool_result.output
                except Exception as e:
                    obs = f"Error: {str(e)}"

            obs = self.truncate_observation(obs)

            step = StepResult(
                thought=step_data.get("thought", ""),
                action=tool_name,
                action_input=tool_input,
                observation=obs,
            )
            steps.append(step)

            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": f"Observation: {obs}\n\nContinue with the next Thought.",
                }
            )

        # 如果迭代次数耗尽，尝试进行一次最终生成
        logger.warning("Agent reached max iterations, attempting final generation")
        final_prompt = FINAL_PROMPT.format(
            conversation_context=conversation_context,
            question=prompt.text,
        )
        messages.append({"role": "user", "content": final_prompt})
        final_response = llm.generate(messages, config=self.llm_config)
        sql = self.extract_sql_from_output(final_response)

        if sql:
            return AgentResult(
                sql=sql, status=SQLStatus.PENDING, steps=steps, tokens_used=total_tokens
            )
        return AgentResult(
            error="Failed to generate SQL",
            status=SQLStatus.INVALID,
            steps=steps,
            tokens_used=total_tokens,
        )

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
        """流式版本：逐步产出中间步骤"""
        yield {"type": "info", "content": "Streaming not yet implemented for ReActAgent"}
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
