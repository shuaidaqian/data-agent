"""结果分析数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class QueryResultPayload:
    """对外返回的受控 SQL 执行结果。"""

    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


@dataclass
class KeyFinding:
    """带证据的关键发现。"""

    claim: str
    evidence: str


@dataclass
class AnalysisResult:
    """基于 SQL 执行结果生成的分析输出。"""

    answer: str
    result: QueryResultPayload
    summary: str
    key_findings: List[KeyFinding] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    followup_questions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
