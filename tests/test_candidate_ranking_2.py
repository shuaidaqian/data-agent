from sql_agent.core.types import ColumnMetadata, TableDescription
from sql_agent.ranking.ranker import CandidateRanker
from sql_agent.semantic.planner import SemanticPlanner
from sql_agent.semantic.registry import SemanticModelRegistry


def test_candidate_ranker_2_explains_verified_selection(sql_database):
    registry = SemanticModelRegistry.from_dict(
        {
            "metrics": [
                {
                    "name": "employee_count",
                    "label": "员工数",
                    "table": "employees",
                    "expression": "COUNT(*)",
                    "synonyms": ["人数"],
                }
            ],
            "dimensions": [
                {
                    "name": "department",
                    "label": "部门",
                    "table": "employees",
                    "column": "department_id",
                    "synonyms": ["部门"],
                }
            ],
        }
    )
    plan = SemanticPlanner(registry).plan("按部门统计员工数")
    ranker = CandidateRanker(
        sql_database,
        _employee_schema(),
        semantic_plan=plan,
        verified_sqls={
            "SELECT department_id, COUNT(*) AS employee_count FROM employees GROUP BY department_id"
        },
    )

    ranked = ranker.rank(
        "按部门统计员工数",
        [
            "SELECT COUNT(*) AS employee_count FROM employees",
            "SELECT department_id, COUNT(*) AS employee_count FROM employees GROUP BY department_id",
        ],
    )

    assert ranked[0].source == "verified"
    assert ranked[0].score_breakdown["verified_query"] > 0
    assert ranked[0].score_breakdown["semantic_plan_match"] > 0
    assert ranked[0].selection_reason
    assert ranked[0].result_shape.valid is True


def test_candidate_ranker_2_marks_group_by_shape_mismatch(sql_database):
    ranker = CandidateRanker(sql_database, _employee_schema())

    ranked = ranker.rank("按部门统计员工数", ["SELECT COUNT(*) AS employee_count FROM employees"])

    assert ranked[0].result_shape.valid is False
    assert "维度" in ranked[0].result_shape.reason


def _employee_schema():
    return [
        TableDescription(
            table_name="employees",
            columns=[
                ColumnMetadata(name="id", data_type="INTEGER"),
                ColumnMetadata(name="department_id", data_type="INTEGER"),
            ],
        )
    ]
