from pathlib import Path

from sql_agent.semantic.compiler import SemanticSQLCompiler
from sql_agent.semantic.planner import SemanticPlanner
from sql_agent.semantic.registry import SemanticModelRegistry


def test_semantic_model_2_loads_governed_metric_and_time_dimension(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_semantic_2_model(tmp_path))

    metric = registry.metric_by_name("paid_order_count")
    time_dimension = registry.dimension_by_name("order_month")

    assert metric.version == "2026-08"
    assert metric.owner == "growth-team"
    assert metric.certified is True
    assert time_dimension.grain == "month"
    assert time_dimension.expr_for_grain("month") == "strftime('%Y-%m', orders.created_at)"


def test_semantic_planner_2_supports_multi_metric_and_time_grain(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_semantic_2_model(tmp_path))

    plan = SemanticPlanner(registry).plan("按月统计支付订单数和销售额趋势")

    assert plan.intent == "metric_query"
    assert [metric.name for metric in plan.metrics] == ["paid_order_count", "gmv"]
    assert [dimension.name for dimension in plan.dimensions] == ["order_month"]
    assert plan.time_grain == "month"
    assert plan.confidence >= 0.85


def test_semantic_compiler_2_compiles_simple_relationship_join(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_semantic_2_model(tmp_path))
    plan = SemanticPlanner(registry).plan("按客户等级统计支付订单数")

    sql = SemanticSQLCompiler(registry).compile(plan)

    assert sql == (
        "SELECT customers.level AS customer_level, COUNT(*) AS paid_order_count "
        "FROM orders JOIN customers ON orders.customer_id = customers.id "
        "WHERE orders.status = 'paid' GROUP BY customers.level"
    )


def test_semantic_planner_2_returns_clarification_for_ambiguous_metric(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_ambiguous_model(tmp_path))

    plan = SemanticPlanner(registry).plan("统计收入")

    assert plan.intent == "NEEDS_CLARIFICATION"
    assert plan.metrics == []
    assert sorted(plan.clarification_options) == ["gross_revenue", "net_revenue"]


def _write_semantic_2_model(tmp_path: Path) -> Path:
    model_path = tmp_path / "semantic_model_2.yml"
    model_path.write_text(
        """
version: 2
db_connection_id: demo
metrics:
  - name: paid_order_count
    label: 支付订单数
    table: orders
    expression: COUNT(*)
    synonyms: ["订单数", "支付订单"]
    version: "2026-08"
    owner: growth-team
    certified: true
    default_filters:
      - field: orders.status
        op: "="
        value: paid
  - name: gmv
    label: 销售额
    table: orders
    expression: SUM(orders.amount)
    synonyms: ["GMV", "成交额"]
    version: "2026-08"
    owner: growth-team
    certified: true
dimensions:
  - name: order_month
    label: 月份
    table: orders
    column: orders.created_at
    type: time
    grain: month
    grain_expressions:
      month: "strftime('%Y-%m', orders.created_at)"
    synonyms: ["按月", "月份", "月度", "趋势"]
  - name: customer_level
    label: 客户等级
    table: customers
    column: customers.level
    synonyms: ["客户等级", "等级"]
relationships:
  - name: orders_customers
    left_table: orders
    right_table: customers
    left_key: orders.customer_id
    right_key: customers.id
""",
        encoding="utf-8",
    )
    return model_path


def _write_ambiguous_model(tmp_path: Path) -> Path:
    model_path = tmp_path / "ambiguous.yml"
    model_path.write_text(
        """
version: 2
metrics:
  - name: gross_revenue
    label: 收入
    table: orders
    expression: SUM(gross_amount)
    synonyms: ["收入"]
  - name: net_revenue
    label: 收入
    table: orders
    expression: SUM(net_amount)
    synonyms: ["收入"]
dimensions: []
""",
        encoding="utf-8",
    )
    return model_path
