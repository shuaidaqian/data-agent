from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

from main import create_app
from tests.fakes import MemoryStorage

Base = declarative_base()


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))


def test_sqlite_mockllm_question_endpoint_uses_stored_connection_and_keeps_history(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "api.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(Employee.__table__.insert(), [{"id": 1, "name": "Alice"}])

    monkeypatch.setenv("LLM_BACKEND", "tests.fakes.MockLLM")
    monkeypatch.setenv("STORAGE_BACKEND", "tests.fakes.MemoryStorage")
    monkeypatch.setenv("VECTOR_BACKEND", "tests.fakes.MemoryVectorStore")
    monkeypatch.setenv("ENABLE_SELF_CORRECTION", "false")
    semantic_model = tmp_path / "semantic_model.yml"
    semantic_model.write_text(
        """
version: 1
db_connection_id: demo
metrics:
  - name: cnt
    label: 员工数量
    table: employees
    expression: COUNT(*)
    synonyms: ["员工数", "人数"]
dimensions: []
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SEMANTIC_MODEL_PATH", str(semantic_model))
    MemoryStorage.reset()

    from sql_agent.api.routes import reset_system

    reset_system()
    client = TestClient(create_app())

    created = client.post(
        "/api/v1/database-connections",
        json={
            "alias": "local-sqlite",
            "connection_uri": f"sqlite:///{db_path}",
            "schemas": ["main"],
        },
    )
    assert created.status_code == 200
    db_connection_id = created.json()["id"]

    first = client.post(
        "/api/v1/question",
        json={
            "question": "员工数量是多少？",
            "db_connection_id": db_connection_id,
            "enable_correction": False,
            "agent_mode": "react",
        },
    )
    assert first.status_code == 200
    body = first.json()
    assert body["answer"] == "当前查询结果为 1。"
    assert body["sql"] == "SELECT COUNT(*) AS cnt FROM employees"
    assert body["result"]["columns"] == ["cnt"]
    assert body["result"]["rows"] == [{"cnt": 1}]
    assert body["semantic_plan"]["metrics"] == ["cnt"]
    assert body["semantic_plan"]["intent"] == "metric_query"
    assert body["visualization"]["chart_type"] == "metric_card"
    assert body["analysis"]["key_findings"][0]["evidence"] == "SQL result: cnt = 1"
    assert body["analysis"]["limitations"]
    assert body["analysis"]["followup_questions"]
    assert body["conversation_id"]
    assert body["candidates"]
    assert body["candidates"][0]["sql"] == "SELECT COUNT(*) AS cnt FROM employees"
    assert body["candidates"][0]["status"] == "VALID"
    assert "执行成功" in body["candidates"][0]["evidence"]

    second = client.post(
        "/api/v1/question",
        json={
            "question": "沿用上一个问题。",
            "db_connection_id": db_connection_id,
            "conversation_id": body["conversation_id"],
            "enable_correction": False,
            "agent_mode": "react",
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == body["conversation_id"]

    conversations = client.get("/api/v1/conversations")
    assert conversations.status_code == 200
    stored = conversations.json()["conversations"]
    assert stored == [body["conversation_id"]]


def test_question_endpoint_returns_404_for_unknown_database(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "tests.fakes.MockLLM")
    monkeypatch.setenv("STORAGE_BACKEND", "tests.fakes.MemoryStorage")
    monkeypatch.setenv("VECTOR_BACKEND", "tests.fakes.MemoryVectorStore")
    MemoryStorage.reset()

    from sql_agent.api.routes import reset_system

    reset_system()
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/question",
        json={"question": "test", "db_connection_id": "missing", "enable_correction": False},
    )
    assert response.status_code == 404


def test_question_endpoint_can_use_grounded_llm_result_analyzer(monkeypatch, tmp_path):
    db_path = tmp_path / "api_llm_analysis.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(Employee.__table__.insert(), [{"id": 1, "name": "Alice"}])

    monkeypatch.setenv("LLM_BACKEND", "tests.fakes.MockLLM")
    monkeypatch.setenv("STORAGE_BACKEND", "tests.fakes.MemoryStorage")
    monkeypatch.setenv("VECTOR_BACKEND", "tests.fakes.MemoryVectorStore")
    monkeypatch.setenv("ENABLE_SELF_CORRECTION", "false")
    monkeypatch.setenv("RESULT_ANALYZER", "llm")
    MemoryStorage.reset()

    from sql_agent.api.routes import reset_system

    reset_system()
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/database-connections",
        json={"alias": "local-sqlite", "connection_uri": f"sqlite:///{db_path}"},
    )
    response = client.post(
        "/api/v1/question",
        json={
            "question": "员工数量是多少？",
            "db_connection_id": created.json()["id"],
            "enable_correction": False,
            "agent_mode": "react",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "当前员工总数为 1 人。"
    assert body["analysis"]["key_findings"][0]["evidence"] == "SQL result: cnt = 1"


def test_feedback_endpoint_creates_verified_query(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "tests.fakes.MockLLM")
    monkeypatch.setenv("STORAGE_BACKEND", "tests.fakes.MemoryStorage")
    monkeypatch.setenv("VECTOR_BACKEND", "tests.fakes.MemoryVectorStore")
    MemoryStorage.reset()

    from sql_agent.api.routes import reset_system

    reset_system()
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/feedback",
        json={
            "question": "员工数量是多少？",
            "db_connection_id": "demo",
            "sql": "SELECT * FROM employees",
            "answer_correct": False,
            "sql_correct": False,
            "wrong_reason": "aggregation",
            "corrected_sql": "SELECT COUNT(*) AS cnt FROM employees",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"]
    verified = client.get("/api/v1/verified-queries", params={"db_connection_id": "demo"})
    assert verified.status_code == 200
    assert verified.json()[0]["sql"] == "SELECT COUNT(*) AS cnt FROM employees"
