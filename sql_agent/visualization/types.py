"""可视化推荐数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class VisualizationRecommendation:
    """基于 SQL result 的确定性可视化建议。"""

    chart_type: str
    title: str
    spec: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
