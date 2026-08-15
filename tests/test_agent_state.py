from __future__ import annotations

from sql_agent.runtime.state import AgentStage, AgentState, AgentStatus


def test_agent_state_tracks_stage_transitions_and_summary():
    state = AgentState(
        question="员工数量是多少？",
        db_connection_id="db1",
        conversation_id="conv1",
    )

    state.transition_to(AgentStage.LOAD_CONTEXT)
    state.transition_to(AgentStage.PLAN_QUERY)
    state.transition_to(AgentStage.FINALIZE, status=AgentStatus.SUCCEEDED)

    payload = state.to_dict()

    assert payload["stage"] == "FINALIZE"
    assert payload["status"] == "SUCCEEDED"
    assert payload["question"] == "员工数量是多少？"
    assert payload["db_connection_id"] == "db1"
    assert payload["conversation_id"] == "conv1"
    assert payload["recovery_attempts"] == 0
    assert payload["error"] is None


def test_agent_state_failed_records_error_and_stage():
    state = AgentState(question="test", db_connection_id="db1")

    state.fail("数据库连接不存在")

    assert state.stage == AgentStage.FAILED
    assert state.status == AgentStatus.FAILED
    assert state.error == "数据库连接不存在"
    assert state.to_dict()["error"] == "数据库连接不存在"
