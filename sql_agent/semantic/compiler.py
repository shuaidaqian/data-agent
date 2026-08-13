"""语义计划到 SQL 的轻量编译器。"""

from __future__ import annotations

from typing import Any

from sql_agent.semantic.registry import SemanticModelRegistry
from sql_agent.semantic.types import SemanticQueryPlan


class SemanticSQLCompiler:
    """将受校验的语义计划编译为简单 SELECT SQL。"""

    def __init__(self, registry: SemanticModelRegistry | None = None):
        self.registry = registry

    def compile(self, plan: SemanticQueryPlan) -> str:
        if not plan.metrics:
            return ""

        base_table = plan.metrics[0].table
        select_parts = [
            f"{dimension.expr_for_grain(plan.time_grain)} AS {dimension.name}"
            for dimension in plan.dimensions
        ]
        select_parts.extend(f"{metric.expression} AS {metric.name}" for metric in plan.metrics)
        sql = f"SELECT {', '.join(select_parts)} FROM {base_table}"
        sql += self._compile_joins(base_table, plan)

        if plan.filters:
            where = " AND ".join(
                f"{filter_item.field} {filter_item.op} {self._format_value(filter_item.value)}"
                for filter_item in plan.filters
            )
            sql += f" WHERE {where}"

        if plan.dimensions:
            group_by = ", ".join(
                dimension.expr_for_grain(plan.time_grain) for dimension in plan.dimensions
            )
            sql += f" GROUP BY {group_by}"

        if plan.order_by:
            order = ", ".join(f"{item.field} {item.direction.upper()}" for item in plan.order_by)
            sql += f" ORDER BY {order}"

        if plan.limit:
            sql += f" LIMIT {plan.limit}"

        return sql

    def _compile_joins(self, base_table: str, plan: SemanticQueryPlan) -> str:
        if not self.registry:
            return ""

        joined_tables = {base_table}
        join_parts = []
        referenced_tables = {dimension.table for dimension in plan.dimensions}
        referenced_tables.update(metric.table for metric in plan.metrics)
        for table in sorted(referenced_tables - {base_table}):
            relationship = self.registry.relationship_for_tables(base_table, table)
            if not relationship or table in joined_tables:
                continue
            join_type = relationship.join_type.upper()
            join_parts.append(
                f" {join_type} {table} ON {relationship.left_key} = {relationship.right_key}"
            )
            joined_tables.add(table)
        return "".join(join_parts)

    def _format_value(self, value: Any) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return f"'{str(value)}'"
