"""
Schema Linking module.

NEW: Improved schema linking for accurate JOIN path detection.
Dataherald's approach only used embedding similarity on individual tables.
This module:
- Identifies foreign key relationships for JOIN path discovery
- Links question entities to schema elements more precisely
- Generates JOIN path suggestions for multi-table queries
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from sql_agent.core.types import TableDescription

logger = logging.getLogger(__name__)


class SchemaLinker:
     """
     Schema linking for NL-to-SQL.

     Key improvements over Dataherald:
     - Explicit FK-based JOIN path discovery
     - Question-to-schema entity linking
     - Multi-table relationship graph building
     """

     def __init__(self, table_descriptions: List[TableDescription]):
         self.tables = table_descriptions
         self._build_relationship_graph()

     def _build_relationship_graph(self) -> None:
         """Build a graph of table relationships"""
         self.adjacency: Dict[str, List[Tuple[str, str, str]]] = {}
         # Maps: table_name -> [(related_table, fk_column, ref_column)]

         for table in self.tables:
             table_key = self._table_key(table)
             if table_key not in self.adjacency:
                 self.adjacency[table_key] = []

             for col in table.columns:
                 if col.is_foreign_key and col.foreign_key_ref:
                     parts = col.foreign_key_ref.split(".")
                     if len(parts) == 3:
                         ref_table = parts[1]
                     else:
                         ref_table = parts[0]
                     self.adjacency[table_key].append(
                         (ref_table, col.name, col.foreign_key_ref)
                     )

     def _table_key(self, table: TableDescription) -> str:
         return f"{table.schema_name}.{table.table_name}" if table.schema_name else table.table_name

     def find_join_paths(
         self, table_names: List[str]
     ) -> List[Dict[str, str]]:
         """
         Find JOIN paths between a set of tables.
         Returns suggested JOIN conditions.
         """
         if len(table_names) < 2:
             return []

         table_set = set(table_names)
         join_paths = []

         for table_name in table_names:
             if table_name in self.adjacency:
                 for related_table, fk_col, ref in self.adjacency[table_name]:
                     if related_table in table_set:
                         join_paths.append({
                             "from_table": table_name,
                             "to_table": related_table,
                             "on_condition": f"{table_name}.{fk_col} = {ref}",
                         })

         return join_paths

     def find_entity_in_schema(
         self, entity: str
     ) -> List[Dict[str, str]]:
         """
         Find schema elements (tables/columns) related to a given entity.
         Uses exact match, case-insensitive, and partial match.
         """
         entity_lower = entity.lower().replace("_", " ")
         matches = []

         for table in self.tables:
             # Match table name
             table_name_lower = table.table_name.lower().replace("_", " ")
             if entity_lower in table_name_lower or table_name_lower in entity_lower:
                 matches.append({
                     "type": "table",
                     "name": self._table_key(table),
                     "relevance": "high",
                 })

             # Match column names
             for col in table.columns:
                 col_name_lower = col.name.lower().replace("_", " ")
                 if entity_lower in col_name_lower or col_name_lower in entity_lower:
                     matches.append({
                         "type": "column",
                         "table": self._table_key(table),
                         "name": col.name,
                         "description": col.description or "",
                         "relevance": "medium",
                     })

         return matches

     def get_join_graph_summary(self) -> str:
         """Get a summary of all relationships for the agent prompt"""
         if not self.adjacency:
             return "No foreign key relationships detected."

         lines = []
         for table, relations in self.adjacency.items():
             if relations:
                 for rel_table, fk_col, ref in relations[:3]:
                     lines.append(f"- {table}.{fk_col} -> {ref}")

         if not lines:
             return "No foreign key relationships detected."
         return "Foreign Key Relationships:\n" + "\n".join(lines)

     def find_join_path_between_tables(
         self, table_a: str, table_b: str
     ) -> Optional[List[str]]:
         """
         BFS between two tables to find a join path through FKs.
         Returns the path of table names.
         """
         if table_a not in self.adjacency or table_b not in self.adjacency:
             return None

         visited = {table_a}
         queue = [[table_a]]

         while queue:
             path = queue.pop(0)
             current = path[-1]

             if current == table_b:
                 return path

             for neighbor, _, _ in self.adjacency.get(current, []):
                 if neighbor not in visited:
                     visited.add(neighbor)
                     new_path = list(path)
                     new_path.append(neighbor)
                     queue.append(new_path)

         return None
