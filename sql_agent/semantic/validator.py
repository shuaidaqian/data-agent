"""语义查询计划校验。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from sql_agent.semantic.registry import SemanticModelRegistry
from sql_agent.semantic.types import SemanticQueryPlan


@dataclass
class SemanticValidationResult:
    """语义计划校验结果。"""

    valid: bool
    errors: List[str] = field(default_factory=list)


class SemanticPlanValidator:
    """校验语义计划只引用语义模型白名单中的对象。"""

    def __init__(self, registry: SemanticModelRegistry):
        self.registry = registry

    def validate(self, plan: SemanticQueryPlan) -> SemanticValidationResult:
        errors = []
        for metric in plan.metrics:
            if not self.registry.metric_by_name(metric.name):
                errors.append(f"Unknown metric: {metric.name}")
        for dimension in plan.dimensions:
            if not self.registry.dimension_by_name(dimension.name):
                errors.append(f"Unknown dimension: {dimension.name}")
        return SemanticValidationResult(valid=not errors, errors=errors)
