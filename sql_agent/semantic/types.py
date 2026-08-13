"""语义层数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SemanticFilter:
    """语义查询中的过滤条件。"""

    field: str
    op: str
    value: Any


@dataclass
class MetricDefinition:
    """业务指标定义。"""

    name: str
    label: str
    table: str
    expression: str
    synonyms: List[str] = field(default_factory=list)
    default_filters: List[SemanticFilter] = field(default_factory=list)
    description: Optional[str] = None
    version: str = "v1"
    owner: str = ""
    certified: bool = False

    def terms(self) -> List[str]:
        return [self.name, self.label, *self.synonyms]


@dataclass
class DimensionDefinition:
    """业务维度定义。"""

    name: str
    label: str
    table: str
    column: str
    synonyms: List[str] = field(default_factory=list)
    description: Optional[str] = None
    type: str = "categorical"
    grain: Optional[str] = None
    grain_expressions: Dict[str, str] = field(default_factory=dict)

    def terms(self) -> List[str]:
        return [self.name, self.label, self.column, *self.synonyms]

    def expr_for_grain(self, grain: Optional[str]) -> str:
        if not grain:
            return self.column
        return self.grain_expressions.get(grain, self.column)


@dataclass
class RelationshipDefinition:
    """语义模型中的简单表关系。"""

    name: str
    left_table: str
    right_table: str
    left_key: str
    right_key: str
    join_type: str = "JOIN"


@dataclass
class SemanticModel:
    """轻量语义模型。"""

    version: int = 1
    db_connection_id: str = ""
    metrics: List[MetricDefinition] = field(default_factory=list)
    dimensions: List[DimensionDefinition] = field(default_factory=list)
    relationships: List[RelationshipDefinition] = field(default_factory=list)


@dataclass
class SemanticOrderBy:
    """语义查询排序。"""

    field: str
    direction: str = "desc"


@dataclass
class SemanticQueryPlan:
    """自然语言问题解析后的语义查询计划。"""

    intent: str
    metrics: List[MetricDefinition] = field(default_factory=list)
    dimensions: List[DimensionDefinition] = field(default_factory=list)
    filters: List[SemanticFilter] = field(default_factory=list)
    order_by: List[SemanticOrderBy] = field(default_factory=list)
    limit: Optional[int] = None
    source: str = "semantic"
    confidence: float = 0.0
    time_grain: Optional[str] = None
    clarification_options: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["metrics"] = [metric.name for metric in self.metrics]
        payload["dimensions"] = [dimension.name for dimension in self.dimensions]
        return payload
