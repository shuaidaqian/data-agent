"""语义查询计划生成器。"""

from __future__ import annotations

import re
from copy import deepcopy

from sql_agent.semantic.registry import SemanticModelRegistry
from sql_agent.semantic.types import SemanticOrderBy, SemanticQueryPlan


class SemanticPlanner:
    """用稳定启发式把自然语言问题解析成语义计划。"""

    def __init__(self, registry: SemanticModelRegistry):
        self.registry = registry

    def plan(self, question: str) -> SemanticQueryPlan:
        metric = self.registry.find_metric(question)
        if not metric:
            return SemanticQueryPlan(intent="unknown", confidence=0.0)

        metric = deepcopy(metric)
        dimension = self.registry.find_dimension(question)
        dimension = deepcopy(dimension) if dimension else None
        filters = deepcopy(metric.default_filters)
        order_by = []
        limit = self._extract_limit(question)
        if limit and self._asks_for_top(question):
            order_by.append(SemanticOrderBy(field=metric.name, direction="desc"))

        return SemanticQueryPlan(
            intent="metric_query",
            metrics=[metric],
            dimensions=[dimension] if dimension else [],
            filters=filters,
            order_by=order_by,
            limit=limit,
            confidence=0.85 if metric else 0.0,
        )

    def _asks_for_top(self, question: str) -> bool:
        return any(token in question.lower() for token in ["top", "最高", "最多", "前"])

    def _extract_limit(self, question: str) -> int | None:
        match = re.search(r"(?:前\s*|top\s*)(\d+)", question, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None
