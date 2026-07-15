"""
Agent Selector

NEW: Automatically selects the best agent mode based on query complexity.
- 'simple' questions: ReAct Agent (fast, lightweight)
- 'medium' questions: ReAct Agent (sufficient with few-shot)
- 'complex' questions: Plan-and-Solve Agent (structured planning)
- User can also force a specific mode via AgentConfig
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
     Routes queries to the appropriate agent based on complexity.

     Complexity estimation considers:
     - Question length and structure
     - Keywords indicating joins, aggregations, or time-series
     - Number of available tables in the schema
     - Whether conversation history exists
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

         # Initialize both agents
         self._react_agent = ReActAgent(system, llm_config, agent_config)
         self._plan_solve_agent = PlanSolveAgent(system, llm_config, agent_config)

     def select_agent(self, complexity: str) -> SQLAgent:
         """Select the appropriate agent based on complexity"""
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
         """Automatically select agent and generate SQL"""
         # Estimate complexity
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
         """Automatically select agent and stream SQL generation"""
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
