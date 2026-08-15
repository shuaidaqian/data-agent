"""候选 SQL 数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CandidateExecution:
    """候选 SQL 的执行证据。"""

    success: bool = False
    row_count: int = 0
    columns: List[str] = field(default_factory=list)
    preview: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ResultShapeValidation:
    """候选 SQL 结果形状校验。"""

    valid: bool = True
    expected: str = ""
    actual: str = ""
    reason: str = ""


@dataclass
class SQLCandidate:
    """可排序、可解释的 SQL 候选。"""

    sql: str
    status: str = "PENDING"
    score: float = 0.0
    evidence: str = ""
    source: str = "agent"
    selection_reason: str = ""
    execution: CandidateExecution = field(default_factory=CandidateExecution)
    score_components: Dict[str, float] = field(default_factory=dict)
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    result_shape: ResultShapeValidation = field(default_factory=ResultShapeValidation)
    safety: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
