"""基于结果形状的可视化推荐器。"""

from __future__ import annotations

from typing import Any, List, Optional

from sql_agent.analysis.types import KeyFinding, QueryResultPayload
from sql_agent.visualization.types import ChartValidation, VisualizationRecommendation


class VisualizationRecommender:
    """根据 SQL result 的列类型和行数生成稳定图表 spec。"""

    def recommend(
        self,
        question: str,
        result: QueryResultPayload,
        findings: Optional[List[KeyFinding]] = None,
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
            return self._line(question, result, time_columns[0], numeric_columns[-1])
        if categorical_columns and numeric_columns:
            if self._asks_for_share(question, findings):
                return self._pie(
                    question, result, categorical_columns[0], numeric_columns[-1], findings
                )
            return self._bar(question, result, categorical_columns[0], numeric_columns[-1])
        return self._table(question, result.columns)

    def validate_chart(
        self,
        chart_type: str,
        result: QueryResultPayload,
        x_field: Optional[str] = None,
        y_field: Optional[str] = None,
    ) -> ChartValidation:
        errors = []
        if x_field and x_field not in result.columns:
            errors.append(f"x 字段 `{x_field}` 不存在。")
        if y_field and y_field not in result.columns:
            errors.append(f"y 字段 `{y_field}` 不存在。")
        if y_field and y_field in result.columns:
            values = [row.get(y_field) for row in result.rows if row.get(y_field) is not None]
            if not values or not all(self._is_number(value) for value in values):
                errors.append(f"y 字段 `{y_field}` 必须是数值。")
        if chart_type == "line" and x_field and not self._is_time_like_field(x_field):
            errors.append("折线趋势图的 x 字段需要是时间字段。")
        return ChartValidation(valid=not errors, errors=errors)

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
            echarts_option={
                "title": {"text": question},
                "series": [
                    {"type": "gauge", "data": [{"name": field, "value": result.rows[0].get(field)}]}
                ],
            },
            validation=ChartValidation(valid=True),
        )

    def _bar(
        self,
        question: str,
        result: QueryResultPayload,
        x_field: str,
        y_field: str,
    ) -> VisualizationRecommendation:
        validation = self.validate_chart("bar", result, x_field=x_field, y_field=y_field)
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
            echarts_option={
                "title": {"text": question},
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": [row.get(x_field) for row in result.rows]},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": y_field,
                        "type": "bar",
                        "data": [row.get(y_field) for row in result.rows],
                    }
                ],
            },
            validation=validation,
        )

    def _line(
        self,
        question: str,
        result: QueryResultPayload,
        x_field: str,
        y_field: str,
    ) -> VisualizationRecommendation:
        validation = self.validate_chart("line", result, x_field=x_field, y_field=y_field)
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
            echarts_option={
                "title": {"text": question},
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": [row.get(x_field) for row in result.rows]},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": y_field,
                        "type": "line",
                        "data": [row.get(y_field) for row in result.rows],
                    }
                ],
            },
            validation=validation,
        )

    def _table(self, question: str, columns: List[str]) -> VisualizationRecommendation:
        return VisualizationRecommendation(
            chart_type="table",
            title=question,
            rationale="当前结果更适合保留为明细表。",
            spec={"columns": columns},
            echarts_option={},
            validation=ChartValidation(valid=True),
        )

    def _pie(
        self,
        question: str,
        result: QueryResultPayload,
        x_field: str,
        y_field: str,
        findings: Optional[List[KeyFinding]],
    ) -> VisualizationRecommendation:
        validation = self.validate_chart("pie", result, x_field=x_field, y_field=y_field)
        return VisualizationRecommendation(
            chart_type="pie",
            title=question,
            rationale="占比或份额问题适合用饼图展示组成结构。",
            spec={
                "type": "pie",
                "encoding": {
                    "category": {"field": x_field, "type": "nominal"},
                    "value": {"field": y_field, "type": "quantitative"},
                },
            },
            echarts_option={
                "title": {"text": question},
                "tooltip": {"trigger": "item"},
                "series": [
                    {
                        "name": y_field,
                        "type": "pie",
                        "data": [
                            {"name": row.get(x_field), "value": row.get(y_field)}
                            for row in result.rows
                        ],
                    }
                ],
            },
            validation=validation,
            supports_finding=bool(findings),
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
        return [column for column in result.columns if self._is_time_like_field(column)]

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _is_time_like_field(self, column: str) -> bool:
        return any(token in column.lower() for token in ["date", "time", "day", "month", "year"])

    def _asks_for_share(
        self,
        question: str,
        findings: Optional[List[KeyFinding]],
    ) -> bool:
        text = question.lower()
        if any(token in text for token in ["占比", "比例", "份额", "share", "proportion"]):
            return True
        return any("占" in finding.claim or "%" in finding.claim for finding in findings or [])
