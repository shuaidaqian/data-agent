"""
复杂 SQL 分解模块。

新增能力：处理 Dataherald 较难稳定覆盖的复杂 SQL 模式：
- 具有非平凡关系的多表 JOIN
- 嵌套子查询
- CTE（公共表表达式）
- 窗口函数
- 复杂聚合

该模块会将复杂查询拆解为更简单的子问题。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sql_agent.llm.base import LLMBackend

logger = logging.getLogger(__name__)


COMPLEX_SQL_PROMPT = """
You are a SQL decomposition expert. Given a complex natural language question,
break it down into simpler sub-questions, then generate the complete SQL.

Question: {question}

Available tables with their columns and relationships:
{schema_info}

Step 1 - Decompose the question into sub-problems:
[List 2-4 sub-questions that together answer the main question]

Step 2 - For each sub-problem, identify:
- Tables needed
- JOIN conditions
- WHERE filters
- Aggregations (if any)

Step 3 - Write the complete SQL:
- Use CTEs (WITH clause) for complex decompositions
- Use proper JOINs with explicit ON conditions
- Use appropriate window functions if needed

Output the final SQL inside a ```sql block.
"""


class ComplexSQLDecomposer:
     """
     将复杂 SQL 查询拆解为更简单的部分。
     使用先分解、再组合的策略。
     """

     def __init__(self, llm: LLMBackend):
         self.llm = llm

     def decompose_and_generate(
         self,
         question: str,
         schema_info: str,
         table_descriptions: List,
     ) -> Optional[Dict[str, Any]]:
         """
         分解复杂问题并生成 SQL。
         返回包含 sql、sub_questions 和 explanation 的字典。
         """
         prompt = COMPLEX_SQL_PROMPT.format(
             question=question,
             schema_info=schema_info,
         )

         response = self.llm.generate([{"role": "user", "content": prompt}])

         # 提取 SQL
         sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL)
         sql = sql_match.group(1).strip() if sql_match else None

         return {
             "sql": sql,
             "raw_response": response,
         }

     @staticmethod
     def is_complex_query(question: str) -> bool:
         """
         使用启发式规则快速判断问题是否需要复杂 SQL。
         """
         text = question.lower()
         complex_indicators = [
             # 多表查询
             " and ", " each ", " per ", " compared to ", " versus ",
             # 聚合
             " average ", " median ", " standard deviation ", " variance ",
             " moving average ", " running total ", " cumulative ",
             # 时间序列
             " month over month", " month-over-month", " quarter over quarter",
             "同比", "环比", " year to date ", " year-over-year ",
             # 排名
             " top 3", " top 5", " top 10", " bottom ", " rank ",
             " highest ", " lowest ", " most ", " least ",
             # 对比
             " percentage ", " proportion ", " ratio ", " share of ",
             " compare ", " difference between ",
         ]
         return any(indicator in text for indicator in complex_indicators)

     @staticmethod
     def get_query_type(question: str) -> str:
         """分类所需 SQL 查询类型"""
         text = question.lower()
         if any(w in text for w in ["month over month", "环比", "同比", "trend", "趋势"]):
             return "time_series"
         if any(w in text for w in ["compare", "对比", "versus", "vs"]):
             return "comparison"
         if any(w in text for w in ["rank", "top", "bottom", "排名"]):
             return "ranking"
         if any(w in text for w in ["percentage", "proportion", "ratio", "占比", "比例"]):
             return "aggregation_ratio"
         return "general"
