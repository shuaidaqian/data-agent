from __future__ import annotations

from sql_agent.ranking.candidate import CandidateExecution, SQLCandidate
from sql_agent.runtime.recovery import RecoveryLoop


def test_recovery_loop_selects_next_valid_candidate_when_best_failed():
    failed = SQLCandidate(
        sql="SELECT missing FROM employees",
        status="INVALID",
        score=0.9,
        evidence="执行失败：no such column: missing",
        execution=CandidateExecution(success=False, error="no such column: missing"),
    )
    valid = SQLCandidate(
        sql="SELECT COUNT(*) AS cnt FROM employees",
        status="VALID",
        score=0.6,
        evidence="执行成功，返回 1 行",
        execution=CandidateExecution(
            success=True, row_count=1, columns=["cnt"], preview=[{"cnt": 1}]
        ),
    )

    decision = RecoveryLoop().recover([failed, valid])

    assert decision.attempted is True
    assert decision.recovered is True
    assert decision.selected_candidate == valid
    assert decision.recovery_attempts == 1
    assert "可执行候选" in decision.reason


def test_recovery_loop_returns_structured_failure_when_no_valid_candidate():
    failed = SQLCandidate(
        sql="DELETE FROM employees",
        status="INVALID",
        evidence="SQL 安全校验失败",
        execution=CandidateExecution(success=False, error="unsafe sql"),
    )

    decision = RecoveryLoop().recover([failed])

    assert decision.attempted is True
    assert decision.recovered is False
    assert decision.selected_candidate is None
    assert decision.recovery_attempts == 1
    assert "没有可恢复" in decision.reason
    assert decision.to_dict()["attempted"] is True
