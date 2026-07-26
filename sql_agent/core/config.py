"""
IoC（控制反转）容器。
所有核心组件都可以通过环境变量替换实现。
设计思路参考 Dataherald config.py 的插件系统。
"""

from __future__ import annotations
import importlib
import inspect
import os as os_module
from abc import ABC
from typing import Dict, Type, TypeVar, cast
from dotenv import load_dotenv

load_dotenv()
_COMPONENT_REGISTRY: Dict[str, str] = {
    "sql_agent.llm.base.LLMBackend": "LLM_BACKEND",
    "sql_agent.storage.db.StorageBackend": "STORAGE_BACKEND",
    "sql_agent.storage.vector.VectorBackend": "VECTOR_BACKEND",
    "sql_agent.context.base.ContextStore": "CONTEXT_STORE",
    "sql_agent.eval.evaluator.Evaluator": "EVALUATOR",
}
_DEFAULT_IMPLS: Dict[str, str] = {
    "sql_agent.llm.base.LLMBackend": "sql_agent.llm.openai_llm.OpenAILLM",
    "sql_agent.storage.db.StorageBackend": "sql_agent.storage.db.MongoStorage",
    "sql_agent.storage.vector.VectorBackend": "sql_agent.storage.vector.ChromaVectorStore",
    "sql_agent.context.base.ContextStore": "sql_agent.context.base.DefaultContextStore",
    "sql_agent.eval.evaluator.Evaluator": "sql_agent.eval.evaluator.SimpleEvaluator",
}
C = TypeVar("C", bound="Component")


def get_class(fqn: str, base_type: Type[C]) -> Type[C]:
    module_name, class_name = fqn.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    if inspect.isclass(base_type) and inspect.isclass(cls) and not issubclass(cls, base_type):
        raise TypeError(f"{fqn} is not a subclass of {get_fqn(base_type)}")
    return cast(Type[C], cls)


def get_fqn(cls: Type[object]) -> str:
    return f"{cls.__module__}.{cls.__name__}"


class Component(ABC):
    _running: bool = False

    def __init__(self, system: "System"):
        self._system = system
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


class Settings:
    def __init__(self):
        self.project_name = os_module.getenv("PROJECT_NAME", "SQL Agent")
        self.debug = os_module.getenv("DEBUG", "false").lower() == "true"
        self.openai_api_key = os_module.getenv("OPENAI_API_KEY")
        self.llm_model = os_module.getenv("LLM_MODEL", "gpt-4o")
        self.llm_temperature = float(os_module.getenv("LLM_TEMPERATURE", "0.0"))
        self.azure_api_key = os_module.getenv("AZURE_API_KEY")
        self.azure_endpoint = os_module.getenv("AZURE_OPENAI_ENDPOINT")
        self.db_uri = os_module.getenv("MONGODB_URI")
        self.db_name = os_module.getenv("MONGODB_DB_NAME", "sql_agent")
        self.embedding_model = os_module.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        self.chroma_persist_dir = os_module.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.agent_mode = os_module.getenv("AGENT_MODE", "auto")
        self.agent_max_iterations = int(os_module.getenv("AGENT_MAX_ITERATIONS", "15"))
        self.engine_timeout = int(os_module.getenv("DH_ENGINE_TIMEOUT", "150"))
        self.upper_limit_rows = int(os_module.getenv("UPPER_LIMIT_QUERY_RETURN_ROWS", "50"))
        self.enable_self_correction = (
            os_module.getenv("ENABLE_SELF_CORRECTION", "true").lower() == "true"
        )
        self.max_correction_rounds = int(os_module.getenv("MAX_CORRECTION_ROUNDS", "3"))
        self.llm_backend = os_module.getenv("LLM_BACKEND", "sql_agent.llm.openai_llm.OpenAILLM")
        self.storage_backend = os_module.getenv(
            "STORAGE_BACKEND", "sql_agent.storage.db.MongoStorage"
        )
        self.vector_backend = os_module.getenv(
            "VECTOR_BACKEND", "sql_agent.storage.vector.ChromaVectorStore"
        )
        self.context_store = os_module.getenv(
            "CONTEXT_STORE", "sql_agent.context.base.DefaultContextStore"
        )
        self.evaluator = os_module.getenv("EVALUATOR", "sql_agent.eval.evaluator.SimpleEvaluator")


class System(Component):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._instances = {}
        super().__init__(self)

    def instance(self, base_type):
        from sql_agent.core.config import _COMPONENT_REGISTRY, _DEFAULT_IMPLS, get_class, get_fqn

        if base_type not in self._instances:
            type_fqn = get_fqn(base_type)
            env_key = _COMPONENT_REGISTRY.get(type_fqn)
            if env_key:
                custom_fqn = getattr(self.settings, env_key.lower(), None) or _DEFAULT_IMPLS.get(
                    type_fqn
                )
                if custom_fqn:
                    impl_class = get_class(custom_fqn, base_type)
                    instance = impl_class(self)
                    self._instances[base_type] = instance
                    if self._running:
                        instance.start()
                    return instance
            raise ValueError(f"Cannot instantiate {base_type}")
        return self._instances[base_type]

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        for inst in self._instances.values():
            inst.stop()
        self._instances.clear()
        self._running = False
