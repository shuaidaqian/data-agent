"""
DAIL-SQL 风格纠错。

灵感来自论文 "DAIL-SQL: Execution-feedback Driven Iterative SQL Refinement"
(https://arxiv.org/abs/2308.02266)

核心思想：先执行 SQL，从数据库（或 LLM）获得反馈，
再根据执行结果迭代改进 SQL。
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from overrides import override

from sql_agent.correction.base import CorrectionResult, SQLCorrector
from sql_agent.core.types import LLMConfig
from sql_agent.sql.database import SQLDatabase, SQLInjectionError

logger = logging.getLogger(__name__)

EXECUTION_FEEDBACK_PROMPT = """
You are a SQL debugger. A SQL query was generated but it has issues.
Analyze the question, the SQL, and the execution feedback to fix it.

Question: {question}
Generated SQL: {sql}
Execution Feedback: {feedback}

Common issues to check:
1. Column/table name correctness (check available schema below)
2. JOIN condition correctness
3. WHERE clause logic
4. GROUP BY / HAVING consistency
5. ORDER BY correctness
6. Aggregation functions usage
7. Data type compatibility

Schema: {schema_info}

Output ONLY the corrected SQL inside a ```sql block.
"""

CONSISTENCY_CHECK_PROMPT = """
Check if this SQL query correctly answers the given question.

Question: {question}
SQL: {sql}

If the SQL fully answers the question, answer: CONSISTENT
If not, explain what is wrong: INCONSISTENT: [reason]

Also verify: the SQL query should be syntactically valid and use only tables/columns that exist.
"""


class DAILStyleCorrector(SQLCorrector):
    """
    受 DAIL-SQL 启发的纠错器。

    使用“执行-反馈-修复”循环：
    1. 执行 SQL，获取错误信息或样例结果
    2. 将错误或结果反馈给 LLM
    3. 让 LLM 给出修复建议
    4. 重复直到 SQL 有效或达到最大轮数
    """

    def __init__(
        self,
        llm_backend,
        database: SQLDatabase,
        llm_config: Optional[LLMConfig] = None,
        max_rounds: int = 3,
    ):
        super().__init__(llm_backend, database, llm_config, max_rounds)

    def _execute_and_get_feedback(self, sql: str) -> Tuple[str, bool]:
        """
        执行 SQL 并返回反馈文本。
        返回值为 (feedback, is_success)。
        """
        try:
            result = self.database.run_sql(sql, top_k=5)
            data = result[1]
            row_count = data.get("row_count", 0)
            columns = data.get("columns", [])
            sample_data = data.get("result", [])[:3]

            feedback = (
                f"Query executed successfully.\n"
                f"Rows returned: {row_count}\n"
                f"Columns: {', '.join(columns)}\n"
            )
            if sample_data:
                feedback += "Sample rows:\n"
                for i, row in enumerate(sample_data[:3], 1):
                    feedback += f"  Row {i}: {row}\n"

            if row_count == 0:
                feedback += (
                    "\nWARNING: Query returned zero rows. Check if the conditions are correct."
                )
                return feedback, True
            return feedback, True
        except SQLInjectionError as e:
            return f"SQL Injection Error: {e}", False
        except Exception as e:
            return f"Execution Error: {str(e)[:300]}", False

    @override
    def correct(
        self,
        question: str,
        sql: str,
        schema_info: Optional[str] = None,
        error: Optional[str] = None,
    ) -> CorrectionResult:
        current_sql = sql
        schema = schema_info or "No schema info"

        for round_num in range(self.max_rounds):
            logger.info(f"DAIL correction round {round_num + 1}/{self.max_rounds}")

            # 执行 SQL 并获取反馈
            feedback, executed = self._execute_and_get_feedback(current_sql)

            if executed and "WARNING" not in feedback:
                # SQL 执行成功后，继续检查是否与用户问题一致
                consistency = self.llm.generate(
                    [
                        {
                            "role": "user",
                            "content": CONSISTENCY_CHECK_PROMPT.format(
                                question=question, sql=current_sql
                            ),
                        }
                    ]
                )

                if "CONSISTENT" in consistency:
                    return CorrectionResult(
                        sql=current_sql,
                        status="VALID",
                        reason="Executed successfully and consistent with question",
                        rounds=round_num + 1,
                        sql_before=sql,
                    )

                feedback += f"\nConsistency check: {consistency[:200]}"
            elif executed and "WARNING" in feedback:
                feedback += "\nNote: Zero rows may indicate incorrect filters or conditions."

            # 根据反馈生成修复版本
            prompt = EXECUTION_FEEDBACK_PROMPT.format(
                question=question,
                sql=current_sql,
                feedback=feedback,
                schema_info=schema[:1500],
            )

            response = self.llm.generate([{"role": "user", "content": prompt}])
            sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL)

            if sql_match:
                current_sql = sql_match.group(1).strip()
                is_valid, val_error = self.validate_sql(current_sql)
                if is_valid:
                    return CorrectionResult(
                        sql=current_sql,
                        status="VALID",
                        reason=f"DAIL corrected after {round_num + 1} rounds with execution feedback",
                        rounds=round_num + 1,
                        sql_before=sql,
                    )

        return CorrectionResult(
            sql=current_sql,
            status="INVALID",
            reason=f"DAIL correction failed after {self.max_rounds} rounds",
            rounds=self.max_rounds,
            sql_before=sql,
        )
