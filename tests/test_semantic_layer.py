from pathlib import Path

from sql_agent.semantic.compiler import SemanticSQLCompiler
from sql_agent.semantic.planner import SemanticPlanner
from sql_agent.semantic.registry import SemanticModelRegistry
from sql_agent.semantic.validator import SemanticPlanValidator


def test_semantic_model_loads_metrics_and_dimensions_from_yaml(tmp_path: Path):
    model_path = tmp_path / "semantic_model.yml"
    model_path.write_text(
        """
version: 1
db_connection_id: demo
metrics:
  - name: employee_count
    label: 员工数量
    table: employees
    expression: COUNT(*)
    synonyms: ["员工数", "人数"]
    default_filters:
      - field: status
        op: "="
        value: active
dimensions:
  - name: department
    label: 部门
    table: employees
    column: department
    synonyms: ["团队"]
""",
        encoding="utf-8",
    )

    registry = SemanticModelRegistry.from_yaml(model_path)

    assert registry.model.db_connection_id == "demo"
    assert registry.find_metric("员工数量是多少？").name == "employee_count"
    assert registry.find_dimension("按部门统计员工数").name == "department"


def test_semantic_planner_builds_metric_plan_with_default_filters(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_demo_model(tmp_path))

    plan = SemanticPlanner(registry).plan("按部门统计员工数量前 3")

    assert plan.intent == "metric_query"
    assert [metric.name for metric in plan.metrics] == ["employee_count"]
    assert [dimension.name for dimension in plan.dimensions] == ["department"]
    assert plan.filters[0].field == "status"
    assert plan.filters[0].value == "active"
    assert plan.order_by[0].field == "employee_count"
    assert plan.order_by[0].direction == "desc"
    assert plan.limit == 3


def test_semantic_validator_rejects_unknown_metric(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_demo_model(tmp_path))
    plan = SemanticPlanner(registry).plan("员工数量是多少？")
    plan.metrics[0].name = "unknown_metric"

    result = SemanticPlanValidator(registry).validate(plan)

    assert not result.valid
    assert "unknown_metric" in result.errors[0]


def test_semantic_sql_compiler_compiles_grouped_metric_query(tmp_path: Path):
    registry = SemanticModelRegistry.from_yaml(_write_demo_model(tmp_path))
    plan = SemanticPlanner(registry).plan("按部门统计员工数量前 3")

    sql = SemanticSQLCompiler().compile(plan)

    assert sql == (
        "SELECT department AS department, COUNT(*) AS employee_count "
        "FROM employees WHERE status = 'active' "
        "GROUP BY department ORDER BY employee_count DESC LIMIT 3"
    )


def _write_demo_model(tmp_path: Path) -> Path:
    model_path = tmp_path / "semantic_model.yml"
    model_path.write_text(
        """
version: 1
db_connection_id: demo
metrics:
  - name: employee_count
    label: 员工数量
    table: employees
    expression: COUNT(*)
    synonyms: ["员工数", "人数"]
    default_filters:
      - field: status
        op: "="
        value: active
dimensions:
  - name: department
    label: 部门
    table: employees
    column: department
    synonyms: ["团队"]
""",
        encoding="utf-8",
    )
    return model_path
