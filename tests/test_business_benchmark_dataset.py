from pathlib import Path

import yaml

from sql_agent.core.types import DatabaseConnection
from sql_agent.eval.demo_business import BusinessDemoBuilder
from sql_agent.semantic.registry import SemanticModelRegistry
from sql_agent.sql.database import SQLDatabase


def test_business_demo_builder_creates_sqlite_database_with_expected_tables(tmp_path: Path):
    db_path = BusinessDemoBuilder(tmp_path).build()
    db = SQLDatabase.get_sql_engine(DatabaseConnection(connection_uri=f"sqlite:///{db_path}"))

    tables = set(db.get_tables_and_views())
    _, result = db.run_sql("SELECT COUNT(*) AS paid_orders FROM orders WHERE status = 'paid'")

    assert {
        "departments",
        "employees",
        "customers",
        "products",
        "orders",
        "order_items",
        "refunds",
        "web_events",
    }.issubset(tables)
    assert result["result"][0]["paid_orders"] > 0


def test_business_semantic_model_loads_metrics_dimensions_and_relationships():
    registry = SemanticModelRegistry.from_yaml("eval_cases/business_semantic_model.yml")

    assert registry.metric_by_name("gmv").certified is True
    assert registry.dimension_by_name("order_month").grain == "month"
    assert registry.relationship_for_tables("orders", "customers") is not None


def test_business_benchmark_has_40_unique_cases_with_required_coverage():
    data = yaml.safe_load(Path("eval_cases/business_benchmark.yml").read_text(encoding="utf-8"))
    cases = data["cases"]
    ids = [case["id"] for case in cases]
    tags = {tag for case in cases for tag in case.get("tags", [])}

    assert len(cases) == 40
    assert len(ids) == len(set(ids))
    assert {
        "basic",
        "semantic",
        "join",
        "trend",
        "analysis",
        "visualization",
        "safety",
    }.issubset(tags)
    assert all(case.get("question") for case in cases)
    assert all(case.get("difficulty") in {"simple", "medium", "hard"} for case in cases)


def test_business_benchmark_golden_sql_executes_for_sql_cases(tmp_path: Path):
    db_path = BusinessDemoBuilder(tmp_path).build()
    db = SQLDatabase.get_sql_engine(DatabaseConnection(connection_uri=f"sqlite:///{db_path}"))
    data = yaml.safe_load(Path("eval_cases/business_benchmark.yml").read_text(encoding="utf-8"))
    executable_cases = [case for case in data["cases"] if case.get("golden_sql")][:10]

    assert executable_cases
    for case in executable_cases:
        _, result = db.run_sql(case["golden_sql"])
        assert result["columns"]
        if case.get("expected_columns"):
            assert set(case["expected_columns"]).issubset(set(result["columns"]))
