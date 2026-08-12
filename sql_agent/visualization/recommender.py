"""基于结果形状的可视化推荐器。"""

from __future__ import annotations

from typing import Any, List

from sql_agent.analysis.types import QueryResultPayload
from sql_agent.visualization.types import VisualizationRecommendation


class VisualizationRecommender:
    """根据 SQL result 的列类型和行数生成稳定图表 spec。"""

    def recommend(
        self,
        question: str,
        result: QueryResultPayload,
    ) -> VisualizationRecommendation:
        if len(result.columns) == 1 and len(result.rows) == 1:
            return self._metric_card(question, result)

        numeric_columns = self._numeric_columns(result)
        time_columns = self._time_columns(result)
        categorical_columns = [
            column
            for column in result.columns
            if column not in numeric_columns and column not in time_columns
        ]

        if time_columns and numeric_columns:
            return self._line(question, time_columns[0], numeric_columns[-1])
        if categorical_columns and numeric_columns:
            return self._bar(question, categorical_columns[0], numeric_columns[-1])
        return self._table(question, result.columns)

    def _metric_card(
        self,
        question: str,
        result: QueryResultPayload,
    ) -> VisualizationRecommendation:
        field = result.columns[0] if result.columns else "value"
        return VisualizationRecommendation(
            chart_type="metric_card",
            title=question,
            rationale="单行单列结果适合用指标卡展示。",
            spec={"value": {"field": field}, "label": field},
        )

    def _bar(self, question: str, x_field: str, y_field: str) -> VisualizationRecommendation:
        return VisualizationRecommendation(
            chart_type="bar",
            title=question,
            rationale="分类维度加数值指标适合用柱状图比较。",
            spec={
                "type": "bar",
                "encoding": {
                    "x": {"field": x_field, "type": "nominal"},
                    "y": {"field": y_field, "type": "quantitative"},
                },
            },
        )

    def _line(self, question: str, x_field: str, y_field: str) -> VisualizationRecommendation:
        return VisualizationRecommendation(
            chart_type="line",
            title=question,
            rationale="时间字段加数值指标适合用折线图观察趋势。",
            spec={
                "type": "line",
                "encoding": {
                    "x": {"field": x_field, "type": "temporal"},
                    "y": {"field": y_field, "type": "quantitative"},
                },
            },
        )

    def _table(self, question: str, columns: List[str]) -> VisualizationRecommendation:
        return VisualizationRecommendation(
            chart_type="table",
            title=question,
            rationale="当前结果更适合保留为明细表。",
            spec={"columns": columns},
        )

    def _numeric_columns(self, result: QueryResultPayload) -> List[str]:
        return [
            column
            for column in result.columns
            if result.rows
            and all(
                self._is_number(row.get(column))
                for row in result.rows
                if row.get(column) is not None
            )
        ]

    def _time_columns(self, result: QueryResultPayload) -> List[str]:
        return [
            column
            for column in result.columns
            if any(token in column.lower() for token in ["date", "time", "day", "month", "year"])
        ]

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
