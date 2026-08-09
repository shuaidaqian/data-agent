from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

from sql_agent.core.config import System
from sql_agent.llm.base import LLMBackend
from sql_agent.storage.db import StorageBackend
from sql_agent.storage.vector import VectorBackend


class MemoryStorage(StorageBackend):
    _collections: Dict[str, Dict[str, Dict[str, Any]]] = {}
    _counter = 0

    def __init__(self, system: System):
        super().__init__(system)

    @classmethod
    def reset(cls) -> None:
        cls._collections = {}
        cls._counter = 0

    def insert(self, collection: str, data: Dict[str, Any]) -> str:
        self.__class__._counter += 1
        record_id = str(data.get("id") or self.__class__._counter)
        row = dict(data)
        row["id"] = record_id
        row.setdefault("_id", record_id)
        self.__class__._collections.setdefault(collection, {})[record_id] = row
        return record_id

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rows = self.find(collection, query)
        return rows[0] if rows else None

    def find(self, collection: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self.__class__._collections.get(collection, {}).values()
        return [dict(row) for row in rows if self._matches(row, query)]

    def update(self, collection: str, query: Dict[str, Any], data: Dict[str, Any]) -> bool:
        changed = False
        for record_id, row in self.__class__._collections.get(collection, {}).items():
            if self._matches(row, query):
                self.__class__._collections[collection][record_id] = {**row, **data}
                changed = True
        return changed

    def delete(self, collection: str, query: Dict[str, Any]) -> bool:
        ids = [
            record_id
            for record_id, row in self.__class__._collections.get(collection, {}).items()
            if self._matches(row, query)
        ]
        for record_id in ids:
            del self.__class__._collections[collection][record_id]
        return bool(ids)

    def _matches(self, row: Dict[str, Any], query: Dict[str, Any]) -> bool:
        return all(row.get(key) == value for key, value in query.items())


class MemoryVectorStore(VectorBackend):
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
        records = self.records.get(collection, [])
        return [
            {"id": str(record.id), "score": 1.0}
            for record in records
            if getattr(record, "db_connection_id", None) == db_connection_id
        ][:num_results]

    def add_records(self, records: List[Any], collection: str):
        self.records.setdefault(collection, []).extend(records)

    def delete_record(self, collection: str, id: str):
        self.records[collection] = [
            record for record in self.records.get(collection, []) if str(record.id) != id
        ]


class MockLLM(LLMBackend):
    def __init__(self, system: System):
        super().__init__(system)
        self.calls = 0

    def generate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        self.calls += 1
        if messages and "严格基于数据证据回答" in messages[0].get("content", ""):
            return """
            {
              "answer": "当前员工总数为 1 人。",
              "summary": "查询返回 cnt = 1。",
              "key_findings": [
                {"claim": "员工总数为 1 人。", "evidence": "SQL result: cnt = 1"}
              ],
              "limitations": ["该结论仅基于当前数据库快照。"],
              "followup_questions": ["是否需要按部门统计员工数量？"]
            }
            """
        return "可以直接查询。\n```sql\nSELECT COUNT(*) AS cnt FROM employees\n```"

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        yield self.generate(messages, config, **kwargs)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def count_tokens(self, text: str) -> int:
        return len(text.split())
