"""
Vector store abstraction.
Supports Chroma, Pinecone, and Astra DB (same as Dataherald).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sql_agent.core.config import Component, System
from sql_agent.core.types import GoldenSQL

logger = logging.getLogger(__name__)


class VectorBackend(Component, ABC):
     """Abstract vector store interface"""

     def __init__(self, system: System):
         super().__init__(system)

     @abstractmethod
     def query(
         self,
         query_texts: List[str],
         db_connection_id: str,
         collection: str,
         num_results: int,
     ) -> List[Dict[str, Any]]:
         ...

     @abstractmethod
     def add_records(self, records: List[Any], collection: str):
         ...

     @abstractmethod
     def delete_record(self, collection: str, id: str):
         ...


class ChromaVectorStore(VectorBackend):
     """ChromaDB vector store implementation"""

     def __init__(self, system: System):
         super().__init__(system)
         import chromadb
         persist = system.settings.chroma_persist_dir
         self.client = chromadb.PersistentClient(path=persist)
         logger.info(f"ChromaDB initialized at: {persist}")

     def query(
         self,
         query_texts: List[str],
         db_connection_id: str,
         collection: str,
         num_results: int,
     ) -> List[Dict[str, Any]]:
         try:
             col = self.client.get_collection(collection)
         except ValueError:
             return []

         results = col.query(
             query_texts=query_texts,
             n_results=num_results,
             where={"db_connection_id": db_connection_id},
         )

         if not results["ids"]:
             return []

         output = []
         for i in range(len(results["ids"][0])):
             output.append({
                 "id": results["ids"][0][i],
                 "score": results["distances"][0][i] if results["distances"] else 0,
             })
         return output

     def add_records(self, records: List[Any], collection: str):
         for record in records:
             self.add_record(record, collection)

     def add_record(self, record: Any, collection: str):
         col = self.client.get_or_create_collection(collection)
         existing = col.get(ids=[str(record.id)])
         if len(existing["documents"]) == 0:
             from sql_metadata import Parser
             tables = ", ".join(Parser(record.sql).tables) if hasattr(record, 'sql') else ""
             col.add(
                 documents=[record.prompt_text],
                 metadatas=[{
                     "tables_used": tables,
                     "db_connection_id": str(record.db_connection_id),
                 }],
                 ids=[str(record.id)],
             )

     def delete_record(self, collection: str, id: str):
         col = self.client.get_or_create_collection(collection)
         col.delete(ids=[id])
