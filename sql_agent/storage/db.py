"""
文档存储抽象层（MongoDB）。
改造自 Dataherald 的 db 模块。
"""

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


class MongoStorage(StorageBackend):
    """MongoDB 存储实现"""

    def __init__(self, system: System):
        super().__init__(system)
        import pymongo

        settings = system.settings
        self.client = pymongo.MongoClient(settings.db_uri)
        self.db = self.client[settings.db_name or "sql_agent"]
        logger.info(f"Connected to MongoDB: {settings.db_name}")

    def insert(self, collection: str, data: Dict[str, Any]) -> str:
        row = dict(data)
        result = self.db[collection].insert_one(row)
        record_id = str(result.inserted_id)
        self.db[collection].update_one({"_id": result.inserted_id}, {"$set": {"id": record_id}})
        return record_id

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        row = self.db[collection].find_one(query)
        return self._normalize(row) if row else None

    def find(self, collection: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [self._normalize(row) for row in self.db[collection].find(query)]

    def update(self, collection: str, query: Dict[str, Any], data: Dict[str, Any]) -> bool:
        result = self.db[collection].update_one(query, {"$set": data})
        return result.modified_count > 0

    def delete(self, collection: str, query: Dict[str, Any]) -> bool:
        result = self.db[collection].delete_one(query)
        return result.deleted_count > 0

    def _normalize(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        if "_id" in data:
            data["_id"] = str(data["_id"])
        if not data.get("id") and data.get("_id"):
            data["id"] = data["_id"]
        return data


class InMemoryStorageBackend:
    """用于本地开发和测试的内存文档存储。"""

    def __init__(self, system: System | None = None):
        self.system = system
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
