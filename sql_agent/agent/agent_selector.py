"""
Agent 选择器。

新增能力：根据查询复杂度自动选择最合适的 Agent 模式。
- simple 问题：ReAct Agent（快速、轻量）
- medium 问题：ReAct Agent（结合 few-shot 通常足够）
- complex 问题：Plan-and-Solve Agent（结构化规划）
- 用户也可以通过 AgentConfig 强制指定模式
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sql_agent.agent.base import AgentResult, SQLAgent, StepResult
from sql_agent.agent.plan_solve_agent import PlanSolveAgent
from sql_agent.agent.react_agent import ReActAgent
from sql_agent.core.types import (
     AgentConfig,
     Conversation,
     DatabaseConnection,
     LLMConfig,
     Prompt,
     TableDescription,
)

logger = logging.getLogger(__name__)


class AgentSelector:
     """
     根据复杂度将查询路由到合适的 Agent。

     复杂度估算会考虑：
     - 问题长度和结构
     - 表示 JOIN、聚合或时间序列的关键词
     - 当前 schema 中可用表数量
     - 是否存在对话历史
     """

     def __init__(
         self,
         system,
         llm_config: Optional[LLMConfig] = None,
         agent_config: Optional[AgentConfig] = None,
     ):
         self.system = system
         self.llm_config = llm_config or LLMConfig()
         self.agent_config = agent_config or AgentConfig()

         # 同时初始化两种 Agent，后续根据复杂度路由
         self._react_agent = ReActAgent(system, llm_config, agent_config)
         self._plan_solve_agent = PlanSolveAgent(system, llm_config, agent_config)

     def select_agent(self, complexity: str) -> SQLAgent:
         """根据复杂度选择合适的 Agent"""
         mode = self.agent_config.mode

         if mode == "react":
             return self._react_agent
         elif mode == "plan_solve":
             return self._plan_solve_agent
         elif mode == "auto":
             if complexity == "complex":
                 logger.info(f"Selected Plan-and-Solve Agent (complexity={complexity})")
                 return self._plan_solve_agent
             else:
                 logger.info(f"Selected ReAct Agent (complexity={complexity})")
                 return self._react_agent
         else:
             logger.warning(f"Unknown mode: {mode}, falling back to ReAct")
             return self._react_agent

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
         """自动选择 Agent 并生成 SQL"""
         # 估算查询复杂度
         complexity = self._react_agent.estimate_complexity(prompt, table_descriptions)
         agent = self.select_agent(complexity)

         return agent.generate_sql(
             prompt=prompt,
             database_connection=database_connection,
             table_descriptions=table_descriptions,
             conversation=conversation,
             few_shot_examples=few_shot_examples,
             instructions=instructions,
             metadata=metadata,
         )

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
         """自动选择 Agent 并流式返回 SQL 生成过程"""
         complexity = self._react_agent.estimate_complexity(prompt, table_descriptions)
         agent = self.select_agent(complexity)
         yield from agent.stream_sql(
             prompt=prompt,
             database_connection=database_connection,
             table_descriptions=table_descriptions,
             conversation=conversation,
             few_shot_examples=few_shot_examples,
             instructions=instructions,
             metadata=metadata,
         )
