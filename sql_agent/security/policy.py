"""SQL AST 安全策略配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SQLSafetyPolicy:
    """SQL 安全策略。"""

    allow_select_only: bool = True
    allow_cte: bool = True
    allow_subquery: bool = True
    allow_select_star: bool = False
    allowed_functions: Optional[List[str]] = None
    denied_functions: List[str] = field(
        default_factory=lambda: [
            "load_extension",
            "pg_read_file",
            "pg_ls_dir",
            "dblink",
        ]
    )
    max_subquery_depth: int = 2
    max_joins: Optional[int] = None
    allowed_schemas: Optional[List[str]] = None
