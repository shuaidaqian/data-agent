"""本地原型使用的文档存储抽象层。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sql_agent.core.config import Component, System

logger = logging.getLogger(__name__)


class StorageBackend(Component, ABC):
    """存储后端抽象接口"""

    def __init__(self, system: System):
        super().__init__(system)

    @abstractmethod
    def insert(self, collection: str, data: Dict[str, Any]) -> str: ...

    @abstractmethod
    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def find(self, collection: str, query: Dict[str, Any]) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def update(self, collection: str, query: Dict[str, Any], data: Dict[str, Any]) -> bool: ...

    @abstractmethod
    def delete(self, collection: str, query: Dict[str, Any]) -> bool: ...


class InMemoryStorageBackend(StorageBackend):
    """用于本地开发和测试的内存文档存储。"""

    def __init__(self, system: System | None = None):
        super().__init__(system)
        self._collections: Dict[str, List[Dict[str, Any]]] = {}
        self._next_id = 1

    def insert(self, collection: str, data: Dict[str, Any]) -> str:
        row = dict(data)
        record_id = str(row.get("id") or self._next_id)
        self._next_id += 1
        row["id"] = record_id
        self._collections.setdefault(collection, []).append(row)
        return record_id

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return next(iter(self.find(collection, query)), None)

    def find(self, collection: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self._collections.get(collection, [])
        return [dict(row) for row in rows if self._matches(row, query)]

    def update(self, collection: str, query: Dict[str, Any], data: Dict[str, Any]) -> bool:
        updated = False
        for row in self._collections.get(collection, []):
            if self._matches(row, query):
                row.update(data)
                updated = True
        return updated

    def delete(self, collection: str, query: Dict[str, Any]) -> bool:
        rows = self._collections.get(collection, [])
        keep = [row for row in rows if not self._matches(row, query)]
        self._collections[collection] = keep
        return len(keep) != len(rows)

    def _matches(self, row: Dict[str, Any], query: Dict[str, Any]) -> bool:
        return all(row.get(key) == value for key, value in query.items())
