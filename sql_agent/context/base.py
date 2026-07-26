"""
ContextStore 抽象层，作用与 Dataherald 的 context_store 类似。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from sql_agent.core.config import Component, System
from sql_agent.core.types import Prompt
from sql_agent.storage.vector import VectorBackend


class ContextStore(Component, ABC):
    """上下文存储抽象接口"""

    def __init__(self, system: System):
        super().__init__(system)
        self.system = system

    @abstractmethod
    def retrieve_context_for_question(
        self, prompt: Prompt, number_of_samples: int = 3
    ) -> Tuple[Optional[List[dict]], Optional[List[dict]]]: ...


class DefaultContextStore(ContextStore):
    """默认上下文存储实现"""

    def __init__(self, system: System):
        super().__init__(system)
        from sql_agent.context.retriever import ContextRetriever
        from sql_agent.storage.db import StorageBackend

        self.vector_store = self.system.instance(VectorBackend)
        self.db_storage = self.system.instance(StorageBackend)
        self.retriever = ContextRetriever(self.vector_store, self.db_storage)

    def retrieve_context_for_question(
        self, prompt: Prompt, number_of_samples: int = 3
    ) -> Tuple[Optional[List[dict]], Optional[List[dict]]]:
        return self.retriever.retrieve_all_context(prompt, number_of_samples)
