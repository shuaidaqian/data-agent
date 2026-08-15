from __future__ import annotations

import os

import pytest

from sql_agent.core.config import Settings, System
from sql_agent.core.types import GoldenSQL
from sql_agent.llm.base import LLMBackend
from sql_agent.storage.db import StorageBackend
from sql_agent.storage.vector import VectorBackend


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_INTEGRATIONS", "false").lower() != "true",
    reason="需要 RUN_REAL_INTEGRATIONS=true 才运行真实外部服务集成测试",
)


def test_real_openai_llm_can_generate_and_embed(monkeypatch):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("缺少 OPENAI_API_KEY")

    monkeypatch.setenv("LLM_BACKEND", "sql_agent.llm.openai_llm.OpenAILLM")
    system = System(Settings())

    llm = system.instance(LLMBackend)
    text = llm.generate(
        [{"role": "user", "content": "只回答 SQL: SELECT 1"}],
    )
    embeddings = llm.embed(["SELECT 1"])

    assert text
    assert embeddings and len(embeddings[0]) > 0


def test_real_mongodb_storage_roundtrip(monkeypatch):
    if not os.getenv("MONGODB_URI"):
        pytest.skip("缺少 MONGODB_URI")

    monkeypatch.setenv("STORAGE_BACKEND", "sql_agent.storage.db.MongoStorage")
    system = System(Settings())
    storage = system.instance(StorageBackend)

    collection = "integration_smoke_tests"
    record_id = storage.insert(collection, {"kind": "mongo-roundtrip", "value": 1})
    found = storage.find_one(collection, {"id": record_id})

    assert found is not None
    assert found["value"] == 1
    assert storage.delete(collection, {"id": record_id})


def test_real_chromadb_vector_store_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_BACKEND", "sql_agent.storage.vector.ChromaVectorStore")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    system = System(Settings())
    vector = system.instance(VectorBackend)

    record = GoldenSQL(
        id="real-chroma-smoke",
        prompt_text="How many employees are there?",
        sql="SELECT COUNT(*) FROM employees",
        db_connection_id="db1",
    )
    vector.add_records([record], "integration_golden_sqls")
    results = vector.query(["employee count"], "db1", "integration_golden_sqls", 1)

    assert results
    assert results[0]["id"] == "real-chroma-smoke"
