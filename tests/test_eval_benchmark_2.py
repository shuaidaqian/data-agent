from pathlib import Path

from sql_agent.eval.harness import EvaluationHarness
from sql_agent.eval.run_api_cases import (
    ApiCaseRunner,
    DemoSQLiteBuilder,
    write_markdown_report,
)


def test_evaluation_harness_2_reports_tag_metrics_and_errors():
    harness = EvaluationHarness.from_cases(
        [
            {
                "id": "case_1",
                "question": "员工数",
                "tags": ["semantic", "grounding"],
                "expected_sql_contains": ["COUNT"],
                "expected_result": {"employee_count": 3},
                "expected_semantic_metrics": ["employee_count"],
                "required_evidence": ["SQL result: employee_count = 3"],
            },
            {
                "id": "case_2",
                "question": "销售额",
                "tags": ["semantic"],
                "expected_sql_contains": ["SUM"],
                "expected_result": {"gmv": 100},
                "expected_semantic_metrics": ["gmv"],
                "required_evidence": ["SQL result: gmv = 100"],
            },
        ]
    )

    report = harness.evaluate_responses(
        {
            "case_1": {
                "status": "VALID",
                "sql": "SELECT COUNT(*) AS employee_count FROM employees",
                "result": {"rows": [{"employee_count": 3}]},
                "semantic_plan": {"metrics": ["employee_count"]},
                "analysis": {"key_findings": [{"evidence": "SQL result: employee_count = 3"}]},
            },
            "case_2": {
                "status": "VALID",
                "sql": "SELECT COUNT(*) AS cnt FROM employees",
                "result": {"rows": [{"gmv": 90}]},
                "semantic_plan": {"metrics": []},
                "analysis": {"key_findings": []},
                "visualization": {"validation": {"valid": False}},
            },
        }
    )

    assert report.tag_metrics["semantic"]["total"] == 2
    assert report.error_breakdown["SQL_INVALID"] == 1
    assert report.error_breakdown["EXECUTION_MISMATCH"] == 1
    assert report.error_breakdown["SEMANTIC_MISS"] == 1
    assert report.error_breakdown["UNGROUNDED_ANSWER"] == 1
    assert report.error_breakdown["WRONG_VISUALIZATION"] == 1


def test_api_case_runner_2_builds_demo_db_and_writes_report(tmp_path: Path):
    db_path = DemoSQLiteBuilder(tmp_path).build()

    assert db_path.exists()

    runner = ApiCaseRunner(api_base_url="http://example.test", db_connection_id="demo")
    payload = runner.build_payload({"id": "c1", "question": "员工数"})

    assert payload["question"] == "员工数"
    assert payload["db_connection_id"] == "demo"

    report_path = write_markdown_report(
        tmp_path,
        "# Report\n\nvalid_rate: 1.00",
        timestamp="20260813-010203",
    )
    assert report_path.name == "20260813-010203.md"
    assert report_path.read_text(encoding="utf-8").startswith("# Report")


def test_business_benchmark_loads_into_harness_with_difficulty_and_safety_status():
    harness = EvaluationHarness.from_yaml("eval_cases/business_benchmark.yml")

    report = harness.evaluate_responses(
        {
            "biz_001_total_paid_orders": {
                "status": "VALID",
                "sql": "SELECT COUNT(*) AS paid_orders FROM orders WHERE status = 'paid'",
                "result": {"rows": [{"paid_orders": 9}], "columns": ["paid_orders"]},
                "analysis": {"key_findings": []},
            },
            "biz_031_unsafe_delete_orders": {
                "status": "BLOCKED",
                "sql": "",
                "result": {"rows": [], "columns": []},
                "analysis": {"key_findings": []},
            },
        }
    )

    assert report.total == 40
    assert report.difficulty_metrics["simple"]["total"] > 0
    assert report.difficulty_metrics["medium"]["total"] > 0
    assert report.difficulty_metrics["hard"]["total"] > 0
    assert report.tag_metrics["safety"]["valid_rate"] > 0
