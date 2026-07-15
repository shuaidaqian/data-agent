"""
Context retriever for few-shot examples and instructions.

Handles:
- Vector similarity search for golden SQLs (same as Dataherald)
- Admin instruction retrieval by db_connection_id
- Schema-aware filtering
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sql_agent.core.types import GoldenSQL, Instruction, Prompt
from sql_agent.storage.vector import VectorBackend

logger = logging.getLogger(__name__)

COLLECTION_GOLDEN_SQL = "golden_sqls"


class ContextRetriever:
     """
     Retrieves context (few-shot examples + instructions) for NL-to-SQL.
     """

     def __init__(
         self,
         vector_store: VectorBackend,
         db_storage: Any,  # StorageBackend
     ):
         self.vector_store = vector_store
         self.db_storage = db_storage

     def retrieve_few_shot_examples(
         self,
         prompt: Prompt,
         number_of_samples: int = 5,
     ) -> Optional[List[Dict[str, Any]]]:
         """
         Retrieve relevant golden SQL examples using vector similarity.
         """
         results = self.vector_store.query(
             query_texts=[prompt.text],
             db_connection_id=prompt.db_connection_id,
             collection=COLLECTION_GOLDEN_SQL,
             num_results=number_of_samples,
         )

         if not results:
             return None

         samples = []
         for res in results:
             # Load full golden SQL from storage
             golden = self.db_storage.find_one(
                 "golden_sqls", {"_id": res.get("id")}
             )
             if golden:
                 samples.append({
                     "prompt_text": golden.get("prompt_text", ""),
                     "sql": golden.get("sql", ""),
                     "score": res.get("score", 0),
                     "tables_used": golden.get("tables_used", []),
                 })

         return samples if samples else None

     def retrieve_instructions(
         self,
         db_connection_id: str,
     ) -> Optional[List[Dict[str, str]]]:
         """
         Retrieve admin instructions for the given database connection.
         """
         instructions = self.db_storage.find(
             "instructions",
             {"db_connection_id": db_connection_id},
         )

         if not instructions:
             return None

         return [{"instruction": inst.get("instruction", "")} for inst in instructions]

     def retrieve_all_context(
         self,
         prompt: Prompt,
         number_of_samples: int = 5,
     ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, str]]]]:
         """
         Convenience method to retrieve both few-shot examples and instructions.
         """
         examples = self.retrieve_few_shot_examples(prompt, number_of_samples)
         instructions = self.retrieve_instructions(prompt.db_connection_id)
         return examples, instructions
