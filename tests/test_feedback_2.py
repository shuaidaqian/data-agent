from sql_agent.feedback.service import FeedbackService
from sql_agent.feedback.types import QueryFeedback, VerifiedQueryLifecycle, WrongReason
from sql_agent.storage.db import InMemoryStorageBackend


def test_feedback_2_records_wrong_reason_and_verified_lifecycle():
    service = FeedbackService(InMemoryStorageBackend())

    feedback_id = service.submit_feedback(
        QueryFeedback(
            question="按部门统计员工数",
            db_connection_id="demo",
            sql="SELECT COUNT(*) FROM employees",
            answer_correct=False,
            sql_correct=False,
            wrong_reason=WrongReason.WRONG_AGGREGATION.value,
            corrected_sql="SELECT department, COUNT(*) AS employee_count FROM employees GROUP BY department",
        )
    )

    verified = service.list_verified_queries("demo")[0]
    assert feedback_id
    assert verified.lifecycle == VerifiedQueryLifecycle.PENDING_REVIEW.value
    assert verified.quality_signals["wrong_reason"] == WrongReason.WRONG_AGGREGATION.value


def test_feedback_2_suggests_semantic_model_update_from_metric_definition_error():
    service = FeedbackService(InMemoryStorageBackend())
    feedback = QueryFeedback(
        question="统计有效订单数",
        db_connection_id="demo",
        sql="SELECT COUNT(*) FROM orders",
        answer_correct=False,
        sql_correct=False,
        wrong_reason=WrongReason.WRONG_METRIC_DEFINITION.value,
        corrected_sql="SELECT COUNT(*) FROM orders WHERE status = 'paid'",
        comment="应该只统计已支付订单",
    )

    suggestions = service.suggest_semantic_updates(feedback)

    assert suggestions
    assert suggestions[0]["type"] == "metric_default_filter"
    assert suggestions[0]["field"] == "status"
    assert suggestions[0]["op"] == "="
    assert suggestions[0]["value"] == "paid"
