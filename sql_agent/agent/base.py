"""
SQL Agent 基类。

为所有 Agent 实现提供基础抽象。
相比 Dataherald 的 SQLGenerator 基类，本版本：
- 与 LangChain 解耦
- 定义清晰的 Agent 接口
- 支持多种 Agent 模式（ReAct、Plan-and-Solve）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from sql_agent.core.config import Component, System
from sql_agent.core.types import (
     AgentConfig,
     Conversation,
     DatabaseConnection,
     GoldenSQL,
     Instruction,
     LLMConfig,
     Prompt,
     SQLGeneration,
     SQLStatus,
     TableDescription,
)

logger = logging.getLogger(__name__)


class StepResult:
     """单个 Agent 步骤的执行结果"""
     thought: str
     action: str
     action_input: str
     observation: str

     def __init__(self, thought: str = "", action: str = "", action_input: str = "", observation: str = ""):
         self.thought = thought
         self.action = action
         self.action_input = action_input
         self.observation = observation


class AgentResult:
     """Agent 执行后的最终结果"""
     sql: str
     status: str
     steps: List[StepResult]
     error: Optional[str]
     tokens_used: int

     def __init__(
         self,
         sql: str = "",
         status: str = SQLStatus.PENDING,
         steps: Optional[List[StepResult]] = None,
         error: Optional[str] = None,
         tokens_used: int = 0,
     ):
         self.sql = sql
         self.status = status
         self.steps = steps or []
         self.error = error
         self.tokens_used = tokens_used


class SQLAgent(Component, ABC):
     """
     所有 SQL 生成 Agent 的抽象基类。

     子类必须实现：
     - generate_sql(): 核心 SQL 生成逻辑
     - stream_sql(): 流式生成版本
     """

     def __init__(
         self,
         system: System,
         llm_config: Optional[LLMConfig] = None,
         agent_config: Optional[AgentConfig] = None,
     ):
         super().__init__(system)
         self.system = system
         self.llm_config = llm_config or LLMConfig()
         self.agent_config = agent_config or AgentConfig()

     @abstractmethod
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
         """根据自然语言生成 SQL"""
         ...

     @abstractmethod
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
         """流式返回 SQL 生成过程"""
         ...

     def estimate_complexity(self, prompt: Prompt, table_descriptions: List[TableDescription]) -> str:
         """
         估算 NL-to-SQL 任务复杂度。
         返回值为：'simple'、'medium' 或 'complex'。
         AgentSelector 会使用该结果决定调用哪种 Agent 模式。
         """
         text = prompt.text.lower()
         complexity_score = 0

         # 表示查询复杂度的关键词
         complex_keywords = [
             "compare", "对比", "average", "平均", "percentage", "百分比",
             "rank", "排名", "top", "bottom", "trend", "趋势",
         ]
         join_keywords = [
             "and", "与", "each", "每个", "per", "每",
             "together", "一起", "combined", "combined", "分别",
         ]
         time_keywords = [
             "month over month", "环比", "year over year", "同比",
             "移动平均", "rolling", "cumulative", "累计",
         ]

         for kw in complex_keywords:
             if kw in text:
                 complexity_score += 1
         for kw in join_keywords:
             if kw in text:
                 complexity_score += 1
         for kw in time_keywords:
             if kw in text:
                 complexity_score += 2

         if len(table_descriptions) > 5:
             complexity_score += 1

         if complexity_score >= 3:
             return "complex"
         elif complexity_score >= 1:
             return "medium"
         return "simple"

     def extract_sql_from_output(self, output: str) -> Optional[str]:
         """从 LLM 输出中提取 SQL（支持 markdown 代码块）"""
         import re
         sql_block_pattern = r"```(?:sql|SQL)?\s*(.*?)\s*```"
         matches = re.findall(sql_block_pattern, output, re.DOTALL)
         for match in matches:
             candidate = match.strip()
             if candidate:
                 return candidate

         fallback = re.search(
             r"\b(SELECT|WITH)\b[\s\S]*?(?=```|$)",
             output,
             re.IGNORECASE,
         )
         return fallback.group(0).strip().rstrip(";") if fallback else None

     def truncate_observation(self, observation: str, max_length: int = 2000) -> str:
         """截断过长的工具观察结果"""
         if len(observation) > max_length:
             return observation[:max_length] + "... (truncated)"
         return observation
