"""
DIN-SQL 风格纠错。

灵感来自论文 "DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction"
(https://arxiv.org/abs/2304.11015)

核心思想：将复杂问题拆解成更简单的子问题，分别求解后再合并结果。
本模块实现的是面向纠错阶段的轻量版本。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from overrides import override

from sql_agent.correction.base import CorrectionResult, SQLCorrector
from sql_agent.core.types import LLMConfig
from sql_agent.sql.database import SQLDatabase

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """
Given a natural language question and a SQL query that may be incorrect,
analyze whether the SQL correctly answers the question.

Question: {question}
Generated SQL: {sql}
Schema Info: {schema_info}
{error_context}

Step 1 - VERIFICATION: Does the SQL query correctly answer the question?
If YES, output "VERIFIED: true" and the original SQL.
If NO, output "VERIFIED: false" and explain what is wrong.

Step 2 - If the SQL is incorrect, identify the specific issue:
- Wrong table or column name?
- Missing or incorrect JOIN condition?
- Wrong aggregation function?
- Missing filter condition?
- Wrong grouping?

Step 3 - FIXED version of the SQL:
Output the corrected SQL inside a ```sql block.
"""


class DINStyleCorrector(SQLCorrector):
     """
     受 DIN-SQL 启发的纠错器。
     
     采用先验证再修复的流程：
     1. 对照问题验证原始 SQL
     2. 识别具体问题（表、列、JOIN、过滤条件）
     3. 生成修正后的版本
     """

     def __init__(
         self,
         llm_backend,
         database: SQLDatabase,
         llm_config: Optional[LLMConfig] = None,
         max_rounds: int = 3,
     ):
         super().__init__(llm_backend, database, llm_config, max_rounds)

     @override
     def correct(
         self,
         question: str,
         sql: str,
         schema_info: Optional[str] = None,
         error: Optional[str] = None,
     ) -> CorrectionResult:
         """应用 DIN-SQL 风格纠错"""
         current_sql = sql
         error_context = ""
         if error:
             error_context = f"Execution Error: {error}"

         for round_num in range(self.max_rounds):
             logger.info(f"DIN correction round {round_num + 1}/{self.max_rounds}")

             # 第 1 步：验证并修复
             prompt = DECOMPOSE_PROMPT.format(
                 question=question,
                 sql=current_sql,
                 schema_info=schema_info or "No schema info available",
                 error_context=error_context,
             )

             response = self.llm.generate([{"role": "user", "content": prompt}])

             # 检查是否已通过验证
             if "VERIFIED: true" in response:
                 # 如果响应中包含 SQL，则提取 SQL；否则继续使用原始 SQL
                 sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL)
                 final_sql = sql_match.group(1).strip() if sql_match else current_sql
                 
                 is_valid, _ = self.validate_sql(final_sql)
                 if is_valid:
                     return CorrectionResult(
                         sql=final_sql,
                         status="VALID",
                         reason="Verified and correct after DIN analysis",
                         rounds=round_num + 1,
                         sql_before=sql,
                     )

             # 提取修正后的 SQL
             sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL)
             if sql_match:
                 current_sql = sql_match.group(1).strip()

             # 校验修正后的 SQL
             is_valid, error_context = self.validate_sql(current_sql)
             if is_valid:
                 return CorrectionResult(
                     sql=current_sql,
                     status="VALID",
                     reason=f"Corrected after {round_num + 1} DIN rounds",
                     rounds=round_num + 1,
                     sql_before=sql,
                 )

         return CorrectionResult(
             sql=current_sql,
             status="INVALID",
             reason=f"Failed to correct after {self.max_rounds} rounds",
             rounds=self.max_rounds,
             sql_before=sql,
         )
