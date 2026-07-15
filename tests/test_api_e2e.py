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
    assert body["sql"] == "SELECT COUNT(*) AS cnt FROM employees"
    assert body["conversation_id"]

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
