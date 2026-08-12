from pathlib import Path

from sql_agent.eval.harness import EvaluationHarness


def test_evaluation_harness_scores_semantic_grounded_response(tmp_path: Path):
    case_path = tmp_path / "cases.yml"
    case_path.write_text(
        """
cases:
  - id: employee_count
    question: 员工数量是多少？
    expected_sql_contains: ["COUNT", "employees"]
    expected_result:
      cnt: 4
    expected_semantic_metrics: ["employee_count"]
    required_evidence: ["SQL result: cnt = 4"]
""",
        encoding="utf-8",
    )
    responses = {
        "employee_count": {
            "sql": "SELECT COUNT(*) AS cnt FROM employees",
            "status": "VALID",
            "result": {"rows": [{"cnt": 4}]},
            "semantic_plan": {"metrics": ["employee_count"]},
            "analysis": {"key_findings": [{"claim": "cnt = 4", "evidence": "SQL result: cnt = 4"}]},
        }
    }

    report = EvaluationHarness.from_yaml(case_path).evaluate_responses(responses)

    assert report.total == 1
    assert report.valid_rate == 1.0
    assert report.execution_accuracy == 1.0
    assert report.answer_grounding_rate == 1.0
    assert report.semantic_plan_accuracy == 1.0
    assert "valid_rate: 1.00" in report.to_markdown()


def test_evaluation_harness_detects_ungrounded_answer(tmp_path: Path):
    case_path = tmp_path / "cases.yml"
    case_path.write_text(
        """
cases:
  - id: employee_count
    question: 员工数量是多少？
    expected_sql_contains: ["COUNT", "employees"]
    expected_result:
      cnt: 4
    expected_semantic_metrics: ["employee_count"]
    required_evidence: ["SQL result: cnt = 4"]
""",
        encoding="utf-8",
    )
    responses = {
        "employee_count": {
            "sql": "SELECT COUNT(*) AS cnt FROM employees",
            "status": "VALID",
            "result": {"rows": [{"cnt": 4}]},
            "semantic_plan": {"metrics": ["employee_count"]},
            "analysis": {"key_findings": [{"claim": "cnt = 4", "evidence": ""}]},
        }
    }

    report = EvaluationHarness.from_yaml(case_path).evaluate_responses(responses)

    assert report.answer_grounding_rate == 0.0
