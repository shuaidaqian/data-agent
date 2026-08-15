from sql_agent.context.base import ContextStore
from sql_agent.core.config import Settings, System
from sql_agent.eval.evaluator import Evaluator
from sql_agent.llm.base import LLMBackend
from sql_agent.storage.db import StorageBackend
from sql_agent.storage.vector import VectorBackend


def test_ioc_can_instantiate_configured_core_components(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "tests.fakes.MockLLM")
    monkeypatch.setenv("STORAGE_BACKEND", "tests.fakes.MemoryStorage")
    monkeypatch.setenv("VECTOR_BACKEND", "tests.fakes.MemoryVectorStore")
    monkeypatch.setenv("CONTEXT_STORE", "sql_agent.context.base.DefaultContextStore")
    monkeypatch.setenv("EVALUATOR", "sql_agent.eval.evaluator.SimpleEvaluator")

    system = System(Settings())

    assert system.instance(LLMBackend).__class__.__name__ == "MockLLM"
    assert system.instance(StorageBackend).__class__.__name__ == "MemoryStorage"
    assert system.instance(VectorBackend).__class__.__name__ == "MemoryVectorStore"
    assert system.instance(ContextStore).__class__.__name__ == "DefaultContextStore"
    assert system.instance(Evaluator).__class__.__name__ == "SimpleEvaluator"


def test_ioc_defaults_point_to_real_adapters(monkeypatch):
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("VECTOR_BACKEND", raising=False)

    settings = Settings()

    assert settings.llm_backend == "sql_agent.llm.openai_llm.OpenAILLM"
    assert settings.storage_backend == "sql_agent.storage.db.MongoStorage"
    assert settings.vector_backend == "sql_agent.storage.vector.ChromaVectorStore"
