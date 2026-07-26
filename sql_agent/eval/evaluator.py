"""
SQL 生成结果评估器。
为生成的 SQL 提供置信度评分。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sql_agent.core.config import Component, System
from sql_agent.core.types import LLMConfig, Prompt, SQLGeneration, SQLStatus

logger = logging.getLogger(__name__)

EVALUATION_PROMPT = """
Evaluate the quality of this SQL query against the user question.

Question: {question}
SQL Query: {sql}

Score each dimension from 0.0 to 1.0:
- Correctness: Does the SQL syntax correctly answer the question?
- Completeness: Does the SQL cover all aspects of the question?
- Efficiency: Is the query reasonably efficient?

Output format:
Correctness: [score]
Completeness: [score]
Efficiency: [score]
Overall: [average]
Feedback: [brief explanation]
"""


class Evaluator(Component):
     """评估生成 SQL 的质量和置信度"""

     def __init__(self, system: System):
         super().__init__(system)
         self.llm = None
         self.llm_config: Optional[LLMConfig] = None

     def get_confidence_score(
         self,
         user_prompt: Prompt,
         sql_generation: SQLGeneration,
         metadata: Optional[Dict[str, Any]] = None,
     ) -> Optional[float]:
         """计算生成 SQL 的置信度分数"""
         if not sql_generation.sql or sql_generation.status in (SQLStatus.INVALID, "INVALID"):
             return 0.0

         if not self.llm:
             from sql_agent.llm.base import LLMBackend
             self.llm = self.system.instance(LLMBackend)

         cfg = self.llm_config or LLMConfig()

         prompt = EVALUATION_PROMPT.format(
             question=user_prompt.text,
             sql=sql_generation.sql,
         )

         try:
             response = self.llm.generate([{"role": "user", "content": prompt}], config=cfg)
             score = self._parse_score(response)
             logger.info(f"Evaluation score: {score}")
             return score
         except Exception as e:
             logger.warning(f"Evaluation failed: {e}")
             return None

     def evaluate(self, sql: str, question: str) -> float:
         """使用统一评估接口评估 SQL"""
         generation = SQLGeneration(prompt_id="", sql=sql, status=SQLStatus.PENDING)
         score = self.get_confidence_score(Prompt(text=question), generation)
         return 0.0 if score is None else score

     def _parse_score(self, response: str) -> Optional[float]:
         """从 LLM 响应中解析总体分数"""
         import re
         match = re.search(r"Overall:\s*([0-9.]+)", response)
         if match:
             return float(match.group(1))
         return None


class SimpleEvaluator(Evaluator):
     """
     简单启发式评估器，用于不希望调用 LLM 评估的场景。
     检查 SQL 语法、关键词存在性和基础结构。
     """

     def __init__(self, system: System):
         super().__init__(system)

     def evaluate(self, sql: str, question: str) -> float:
         """简单启发式打分"""
         score = 0.5  # 基础分

         # 包含 SELECT 时加分，表示基本像一个查询
         if "SELECT" in sql.upper():
             score += 0.2
         else:
             score -= 0.3

         # 对常见结构问题扣分
         if "FROM" not in sql.upper():
             score -= 0.2

         if ";" in sql.rstrip()[:-1]:
             score -= 0.1

         return max(0.0, min(1.0, score))
