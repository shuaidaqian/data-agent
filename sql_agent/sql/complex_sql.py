"""
Complex SQL decomposition module.

NEW: Handles complex SQL patterns that Dataherald struggles with:
- Multi-table JOINs with non-trivial relationships
- Nested subqueries
- CTEs (Common Table Expressions)
- Window functions
- Complex aggregations

Decomposes complex queries into simpler sub-problems.
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
     Decomposes complex SQL queries into simpler parts.
     Uses a decompose-then-compose strategy.
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
         Decompose a complex question and generate SQL.
         Returns dict with 'sql', 'sub_questions', and 'explanation'.
         """
         prompt = COMPLEX_SQL_PROMPT.format(
             question=question,
             schema_info=schema_info,
         )

         response = self.llm.generate([{"role": "user", "content": prompt}])

         # Extract SQL
         sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL)
         sql = sql_match.group(1).strip() if sql_match else None

         return {
             "sql": sql,
             "raw_response": response,
         }

     @staticmethod
     def is_complex_query(question: str) -> bool:
         """
         Quick heuristic check if a question requires complex SQL.
         """
         text = question.lower()
         complex_indicators = [
             # Multi-table
             " and ", " each ", " per ", " compared to ", " versus ",
             # Aggregations
             " average ", " median ", " standard deviation ", " variance ",
             " moving average ", " running total ", " cumulative ",
             # Time series
             " month over month", " month-over-month", " quarter over quarter",
             "同比", "环比", " year to date ", " year-over-year ",
             # Ranking
             " top 3", " top 5", " top 10", " bottom ", " rank ",
             " highest ", " lowest ", " most ", " least ",
             # Comparisons
             " percentage ", " proportion ", " ratio ", " share of ",
             " compare ", " difference between ",
         ]
         return any(indicator in text for indicator in complex_indicators)

     @staticmethod
     def get_query_type(question: str) -> str:
         """Classify the type of SQL query needed"""
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
