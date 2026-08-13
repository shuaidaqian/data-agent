"""可视化推荐数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class ChartValidation:
    """图表字段校验结果。"""

    valid: bool = True
    errors: List[str] = field(default_factory=list)


@dataclass
class VisualizationRecommendation:
    """基于 SQL result 的确定性可视化建议。"""

    chart_type: str
    title: str
    spec: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    echarts_option: Dict[str, Any] = field(default_factory=dict)
    validation: ChartValidation = field(default_factory=ChartValidation)
    supports_finding: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
