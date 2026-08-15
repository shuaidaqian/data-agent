"""SQL AST 安全校验数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SQLViolationType(str, Enum):
    """SQL 安全违规类型。"""

    PARSE_ERROR = "PARSE_ERROR"
    NON_SELECT_STATEMENT = "NON_SELECT_STATEMENT"
    MULTI_STATEMENT = "MULTI_STATEMENT"
    UNKNOWN_TABLE = "UNKNOWN_TABLE"
    UNKNOWN_COLUMN = "UNKNOWN_COLUMN"
    AMBIGUOUS_COLUMN = "AMBIGUOUS_COLUMN"
    STAR_NOT_ALLOWED = "STAR_NOT_ALLOWED"
    FUNCTION_NOT_ALLOWED = "FUNCTION_NOT_ALLOWED"
    SUBQUERY_NOT_ALLOWED = "SUBQUERY_NOT_ALLOWED"
    CTE_NOT_ALLOWED = "CTE_NOT_ALLOWED"
    CROSS_SCHEMA_ACCESS = "CROSS_SCHEMA_ACCESS"
    UNSUPPORTED_SQL = "UNSUPPORTED_SQL"


class SQLRiskLevel(str, Enum):
    """SQL 风险等级。"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


@dataclass
class SQLSafetyViolation:
    """单条 SQL 安全违规。"""

    type: str
    message: str
    identifier: Optional[str] = None
    table: Optional[str] = None
    column: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SQLSafetyReport:
    """SQL 安全校验报告。"""

    allowed: bool
    risk_level: str
    sql: str
    normalized_sql: str = ""
    tables: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    violations: List[SQLSafetyViolation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["violations"] = [violation.to_dict() for violation in self.violations]
        return payload

    def to_message(self) -> str:
        if self.allowed:
            return "SQL AST 安全校验通过"
        reasons = "；".join(violation.message for violation in self.violations)
        return f"SQL AST 安全校验失败：{reasons}"
