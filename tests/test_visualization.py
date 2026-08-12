from sql_agent.analysis.types import QueryResultPayload
from sql_agent.visualization.recommender import VisualizationRecommender


def test_visualization_recommender_returns_metric_card_for_single_value():
    result = QueryResultPayload(
        columns=["employee_count"], rows=[{"employee_count": 4}], row_count=1
    )

    recommendation = VisualizationRecommender().recommend("员工数量是多少？", result)

    assert recommendation.chart_type == "metric_card"
    assert recommendation.spec["value"]["field"] == "employee_count"


def test_visualization_recommender_returns_bar_for_category_metric_rows():
    result = QueryResultPayload(
        columns=["department", "employee_count"],
        rows=[
            {"department": "Engineering", "employee_count": 2},
            {"department": "Sales", "employee_count": 1},
        ],
        row_count=2,
    )

    recommendation = VisualizationRecommender().recommend("按部门统计员工数量", result)

    assert recommendation.chart_type == "bar"
    assert recommendation.spec["encoding"]["x"]["field"] == "department"
    assert recommendation.spec["encoding"]["y"]["field"] == "employee_count"


def test_visualization_recommender_returns_line_for_time_series():
    result = QueryResultPayload(
        columns=["sale_date", "amount"],
        rows=[
            {"sale_date": "2026-08-01", "amount": 100},
            {"sale_date": "2026-08-02", "amount": 120},
        ],
        row_count=2,
    )

    recommendation = VisualizationRecommender().recommend("按日期查看销售额趋势", result)

    assert recommendation.chart_type == "line"
    assert recommendation.spec["encoding"]["x"]["field"] == "sale_date"
    assert recommendation.spec["encoding"]["y"]["field"] == "amount"


def test_visualization_recommender_returns_table_for_non_numeric_rows():
    result = QueryResultPayload(
        columns=["name", "department"],
        rows=[{"name": "Alice", "department": "Engineering"}],
        row_count=1,
    )

    recommendation = VisualizationRecommender().recommend("查看员工明细", result)

    assert recommendation.chart_type == "table"
    assert recommendation.spec["columns"] == ["name", "department"]
