from sql_agent.feedback.service import FeedbackService
from sql_agent.feedback.types import QueryFeedback
from sql_agent.core.config import Settings, System
from tests.fakes import MemoryStorage


def test_feedback_service_saves_query_feedback():
    MemoryStorage.reset()
    service = FeedbackService(_memory_storage())

    feedback_id = service.submit_feedback(
        QueryFeedback(
            question="员工数量是多少？",
            db_connection_id="demo",
            sql="SELECT COUNT(*) AS employee_count FROM employees",
            answer_correct=True,
            sql_correct=True,
            comment="结果正确",
        )
    )

    rows = service.list_feedback("demo")
    assert feedback_id
    assert rows[0].question == "员工数量是多少？"
    assert rows[0].answer_correct is True


def test_feedback_with_corrected_sql_creates_verified_query():
    MemoryStorage.reset()
    service = FeedbackService(_memory_storage())

    service.submit_feedback(
        QueryFeedback(
            question="员工数量是多少？",
            db_connection_id="demo",
            sql="SELECT * FROM employees",
            answer_correct=False,
            sql_correct=False,
            wrong_reason="aggregation",
            corrected_sql="SELECT COUNT(*) AS employee_count FROM employees",
        )
    )

    verified = service.list_verified_queries("demo")
    assert len(verified) == 1
    assert verified[0].question == "员工数量是多少？"
    assert verified[0].sql == "SELECT COUNT(*) AS employee_count FROM employees"


def test_feedback_service_retrieves_similar_verified_queries():
    MemoryStorage.reset()
    service = FeedbackService(_memory_storage())
    service.submit_feedback(
        QueryFeedback(
            question="员工数量是多少？",
            db_connection_id="demo",
            sql="SELECT * FROM employees",
            answer_correct=False,
            sql_correct=False,
            corrected_sql="SELECT COUNT(*) AS employee_count FROM employees",
        )
    )

    matches = service.retrieve_verified_queries("统计员工数量", "demo", limit=1)

    assert len(matches) == 1
    assert matches[0].sql == "SELECT COUNT(*) AS employee_count FROM employees"
    assert matches[0].score > 0


def _memory_storage() -> MemoryStorage:
    return MemoryStorage(System(Settings()))
