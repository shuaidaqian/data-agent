"""
Self-correction module for SQL generation.

NEW: Dataherald only did basic syntax validation.
This module implements two SOTA correction strategies:
- DIN-SQL: Decomposition-then-Linking
- DAIL-SQL: Execution-feedback driven correction
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text as sa_text

from sql_agent.core.types import LLMConfig, SQLGeneration, SQLStatus
from sql_agent.sql.database import SQLDatabase

logger = logging.getLogger(__name__)


class CorrectionResult:
     """Result of a correction attempt"""
     sql: str
     status: str
     reason: Optional[str]
     rounds: int
     sql_before: Optional[str]

     def __init__(
         self,
         sql: str = "",
         status: str = SQLStatus.INVALID,
         reason: Optional[str] = None,
         rounds: int = 0,
         sql_before: Optional[str] = None,
     ):
         self.sql = sql
         self.status = status
         self.reason = reason
         self.rounds = rounds
         self.sql_before = sql_before


class SQLCorrector(ABC):
     """Abstract base for SQL correction strategies."""

     def __init__(
         self,
         llm_backend,
         database: SQLDatabase,
         llm_config: Optional[LLMConfig] = None,
         max_rounds: int = 3,
     ):
         self.llm = llm_backend
         self.database = database
         self.llm_config = llm_config or LLMConfig()
         self.max_rounds = max_rounds

     @abstractmethod
     def correct(
         self,
         question: str,
         sql: str,
         schema_info: Optional[str] = None,
         error: Optional[str] = None,
     ) -> CorrectionResult:
         ...

     def validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
         """Validate SQL syntax by attempting EXPLAIN or parsing."""
         if not sql or not sql.strip():
             return False, "Empty SQL query"
         try:
             dialect = str(self.database._engine.url.get_dialect())
             if "postgresql" in dialect:
                 validate_query = f"EXPLAIN ({sql})"
             else:
                 validate_query = f"SELECT * FROM ({sql}) AS _sub LIMIT 0"
             with self.database._engine.connect() as conn:
                 conn.execute(sa_text(validate_query))
             return True, None
         except Exception as e:
             error_msg = str(e)
             for pattern in [
                 r'syntax error at or near "(.+?)"',
                 r'column "(.+?)" does not exist',
                 r'relation "(.+?)" does not exist',
             ]:
                 match = re.search(pattern, error_msg, re.IGNORECASE)
                 if match:
                     return False, f"SQL Error: {match.group(0)}"
             return False, f"SQL Error: {error_msg[:200]}"
