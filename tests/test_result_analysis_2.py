from sql_agent.analysis.result_analyzer import HeuristicResultAnalyzer
from sql_agent.analysis.types import FindingType
from sql_agent.ranking.candidate import CandidateExecution, SQLCandidate


def test_result_analyzer_2_generates_top_k_and_share_findings():
    candidate = SQLCandidate(
        sql="SELECT department, employee_count FROM metrics ORDER BY employee_count DESC",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=3,
            columns=["department", "employee_count"],
            preview=[
                {"department": "研发", "employee_count": 60},
                {"department": "销售", "employee_count": 30},
                {"department": "客服", "employee_count": 10},
            ],
        ),
    )

    analysis = HeuristicResultAnalyzer().analyze("各部门员工数 Top 3", candidate)

    finding_types = [finding.finding_type for finding in analysis.key_findings]
    assert FindingType.TOP_K.value in finding_types
    assert FindingType.COMPARISON.value in finding_types
    assert any("60.00%" in finding.claim for finding in analysis.key_findings)
    assert all(finding.evidence.startswith("SQL result:") for finding in analysis.key_findings)


def test_result_analyzer_2_adds_causality_limitation_for_why_question():
    candidate = SQLCandidate(
        sql="SELECT department, employee_count FROM metrics",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=1,
            columns=["department", "employee_count"],
            preview=[{"department": "研发", "employee_count": 60}],
        ),
    )

    analysis = HeuristicResultAnalyzer().analyze("为什么研发人数最多", candidate)

    assert any("因果" in limitation or "原因" in limitation for limitation in analysis.limitations)
