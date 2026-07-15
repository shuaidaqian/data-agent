"""
Base SQL Agent class.

Provides the foundation for all agent implementations.
Compared to Dataherald's SQLGenerator base, this version:
- Decouples from LangChain
- Defines a clean agent interface
- Supports multiple agent modes (ReAct, Plan-and-Solve)
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
     """Result of a single agent step"""
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
     """Final result from agent execution"""
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
     Abstract base class for all SQL generation agents.

     Subclasses must implement:
     - generate_sql(): The core SQL generation logic
     - stream_sql(): Streaming version
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
         """Generate SQL from natural language"""
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
         """Stream SQL generation process"""
         ...

     def estimate_complexity(self, prompt: Prompt, table_descriptions: List[TableDescription]) -> str:
         """
         Estimate the complexity of a NL-to-SQL task.
         Returns: 'simple', 'medium', or 'complex'
         Used by AgentSelector to decide which agent mode to use.
         """
         text = prompt.text.lower()
         complexity_score = 0

         # Keywords indicating complexity
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
         """Extract SQL from LLM output (handles markdown code blocks)"""
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
         """Truncate long observations"""
         if len(observation) > max_length:
             return observation[:max_length] + "... (truncated)"
         return observation
