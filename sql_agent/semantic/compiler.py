"""语义计划到 SQL 的轻量编译器。"""

from __future__ import annotations

from typing import Any

from sql_agent.semantic.types import SemanticQueryPlan


class SemanticSQLCompiler:
    """将受校验的语义计划编译为简单 SELECT SQL。"""

    def compile(self, plan: SemanticQueryPlan) -> str:
        if not plan.metrics:
            return ""

        metric = plan.metrics[0]
        select_parts = [f"{dimension.column} AS {dimension.name}" for dimension in plan.dimensions]
        select_parts.append(f"{metric.expression} AS {metric.name}")
        sql = f"SELECT {', '.join(select_parts)} FROM {metric.table}"

        if plan.filters:
            where = " AND ".join(
                f"{filter_item.field} {filter_item.op} {self._format_value(filter_item.value)}"
                for filter_item in plan.filters
            )
            sql += f" WHERE {where}"

        if plan.dimensions:
            group_by = ", ".join(dimension.column for dimension in plan.dimensions)
            sql += f" GROUP BY {group_by}"

        if plan.order_by:
            order = ", ".join(f"{item.field} {item.direction.upper()}" for item in plan.order_by)
            sql += f" ORDER BY {order}"

        if plan.limit:
            sql += f" LIMIT {plan.limit}"

        return sql

    def _format_value(self, value: Any) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return f"'{str(value)}'"
