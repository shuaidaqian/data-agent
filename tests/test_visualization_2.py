from sql_agent.analysis.types import KeyFinding, QueryResultPayload
from sql_agent.visualization.recommender import VisualizationRecommender


def test_visualization_2_returns_valid_echarts_bar_option():
    result = QueryResultPayload(
        columns=["department", "employee_count"],
        rows=[
            {"department": "研发", "employee_count": 60},
            {"department": "销售", "employee_count": 30},
        ],
        row_count=2,
    )

    recommendation = VisualizationRecommender().recommend("按部门统计员工数", result)

    assert recommendation.chart_type == "bar"
    assert recommendation.validation.valid is True
    assert recommendation.echarts_option["xAxis"]["data"] == ["研发", "销售"]
    assert recommendation.echarts_option["series"][0]["data"] == [60, 30]


def test_visualization_2_rejects_line_chart_without_time_like_x():
    result = QueryResultPayload(
        columns=["department", "employee_count"],
        rows=[{"department": "研发", "employee_count": 60}],
        row_count=1,
    )

    validation = VisualizationRecommender().validate_chart(
        "line",
        result,
        x_field="department",
        y_field="employee_count",
    )

    assert validation.valid is False
    assert "时间" in validation.errors[0]


def test_visualization_2_supports_finding_for_share_pie():
    result = QueryResultPayload(
        columns=["department", "employee_count"],
        rows=[
            {"department": "研发", "employee_count": 60},
            {"department": "销售", "employee_count": 40},
        ],
        row_count=2,
    )
    finding = KeyFinding(
        claim="研发占比 60.00%", evidence="SQL result: 研发 = 60", finding_type="comparison"
    )

    recommendation = VisualizationRecommender().recommend("各部门占比", result, findings=[finding])

    assert recommendation.chart_type == "pie"
    assert recommendation.supports_finding is True
    assert recommendation.echarts_option["series"][0]["type"] == "pie"
