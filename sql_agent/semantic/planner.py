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
        metrics = self.registry.find_metrics(question)
        if self._is_ambiguous(metrics):
            return SemanticQueryPlan(
                intent="NEEDS_CLARIFICATION",
                confidence=0.2,
                clarification_options=[metric.name for metric in metrics],
            )
        if not metrics:
            return SemanticQueryPlan(intent="unknown", confidence=0.0)

        metrics = [deepcopy(metric) for metric in metrics]
        dimensions = [deepcopy(dimension) for dimension in self.registry.find_dimensions(question)]
        filters = []
        for metric in metrics:
            filters.extend(deepcopy(metric.default_filters))
        order_by = []
        limit = self._extract_limit(question)
        if limit and self._asks_for_top(question):
            order_by.append(SemanticOrderBy(field=metrics[0].name, direction="desc"))

        return SemanticQueryPlan(
            intent="metric_query",
            metrics=metrics,
            dimensions=dimensions,
            filters=filters,
            order_by=order_by,
            limit=limit,
            confidence=0.85 if metrics else 0.0,
            time_grain=self._detect_time_grain(question, dimensions),
        )

    def _asks_for_top(self, question: str) -> bool:
        return any(token in question.lower() for token in ["top", "最高", "最多", "前"])

    def _extract_limit(self, question: str) -> int | None:
        match = re.search(r"(?:前\s*|top\s*)(\d+)", question, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _detect_time_grain(self, question: str, dimensions) -> str | None:
        text = question.lower()
        for grain, terms in [
            ("quarter", ["quarter", "季度", "按季"]),
            ("month", ["month", "月份", "按月", "月度"]),
            ("year", ["year", "年份", "按年", "年度"]),
            ("day", ["day", "日期", "按日", "每天"]),
        ]:
            if any(term in text for term in terms):
                return grain
        for dimension in dimensions:
            if dimension.type == "time" and dimension.grain:
                return dimension.grain
        return None

    def _is_ambiguous(self, metrics) -> bool:
        if len(metrics) <= 1:
            return False
        term_sets = [set(term.lower() for term in metric.terms() if term) for metric in metrics]
        return any(term_sets[0] & term_set for term_set in term_sets[1:])
