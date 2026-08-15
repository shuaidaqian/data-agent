"""本地原型使用的向量存储抽象层。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sql_agent.core.config import Component, System

logger = logging.getLogger(__name__)


class VectorBackend(Component, ABC):
    """向量存储抽象接口"""

    def __init__(self, system: System):
        super().__init__(system)

    @abstractmethod
    def query(
        self,
        query_texts: List[str],
        db_connection_id: str,
        collection: str,
        num_results: int,
    ) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def add_records(self, records: List[Any], collection: str): ...

    @abstractmethod
    def delete_record(self, collection: str, id: str): ...


class InMemoryVectorStore(VectorBackend):
    """用于本地原型的内存向量检索替身。"""

    def __init__(self, system: System):
        super().__init__(system)
        self.records: Dict[str, List[Any]] = {}

    def query(
        self,
        query_texts: List[str],
        db_connection_id: str,
        collection: str,
        num_results: int,
    ) -> List[Dict[str, Any]]:
        query_text = " ".join(query_texts).lower()
        scored = []
        for record in self.records.get(collection, []):
            if str(getattr(record, "db_connection_id", "")) != str(db_connection_id):
                continue
            text = f"{getattr(record, 'prompt_text', '')} {getattr(record, 'sql', '')}".lower()
            score = self._token_overlap(query_text, text)
            scored.append({"id": str(getattr(record, "id", "")), "score": score})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:num_results]

    def add_records(self, records: List[Any], collection: str):
        self.records.setdefault(collection, []).extend(records)

    def delete_record(self, collection: str, id: str):
        self.records[collection] = [
            record for record in self.records.get(collection, []) if str(record.id) != id
        ]

    def _token_overlap(self, left: str, right: str) -> float:
        left_tokens = {token for token in left.split() if token}
        right_tokens = {token for token in right.split() if token}
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
