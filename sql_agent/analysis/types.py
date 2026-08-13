"""结果分析数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FindingType(str, Enum):
    """结果分析发现类型。"""

    SINGLE_METRIC = "single_metric"
    TOP_K = "top_k"
    COMPARISON = "comparison"
    TREND = "trend"
    DISTRIBUTION = "distribution"
    EMPTY_RESULT = "empty_result"
    DATA_QUALITY_WARNING = "data_quality_warning"


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
    finding_type: str = FindingType.SINGLE_METRIC.value


@dataclass
class AnalysisResult:
    """基于 SQL 执行结果生成的分析输出。"""

    answer: str
    result: QueryResultPayload
    summary: str
    key_findings: List[KeyFinding] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    followup_questions: List[str] = field(default_factory=list)
    visualization: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
