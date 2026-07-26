"""
Schema Linking 模块。

新增能力：增强 schema linking，用于更准确地检测 JOIN 路径。
Dataherald 原始方案主要对单表做 embedding 相似度检索。
本模块提供：
- 识别外键关系，用于发现 JOIN 路径
- 更精确地将问题实体链接到 schema 元素
- 为多表查询生成 JOIN 路径建议
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from sql_agent.core.types import TableDescription

logger = logging.getLogger(__name__)


class SchemaLinker:
    """
    面向 NL-to-SQL 的 Schema Linking。

    相比 Dataherald 的关键改进：
    - 基于显式外键发现 JOIN 路径
    - 将问题实体链接到 schema
    - 构建多表关系图
    """

    def __init__(self, table_descriptions: List[TableDescription]):
        self.tables = table_descriptions
        self._build_relationship_graph()

    def _build_relationship_graph(self) -> None:
        """构建表关系图"""
        self.adjacency: Dict[str, List[Tuple[str, str, str]]] = {}
        # 映射：table_name -> [(related_table, fk_column, ref_column)]

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
                    self.adjacency[table_key].append((ref_table, col.name, col.foreign_key_ref))

    def _table_key(self, table: TableDescription) -> str:
        return f"{table.schema_name}.{table.table_name}" if table.schema_name else table.table_name

    def find_join_paths(self, table_names: List[str]) -> List[Dict[str, str]]:
        """
        在一组表之间查找 JOIN 路径。
        返回建议的 JOIN 条件。
        """
        if len(table_names) < 2:
            return []

        table_set = set(table_names)
        join_paths = []

        for table_name in table_names:
            if table_name in self.adjacency:
                for related_table, fk_col, ref in self.adjacency[table_name]:
                    if related_table in table_set:
                        join_paths.append(
                            {
                                "from_table": table_name,
                                "to_table": related_table,
                                "on_condition": f"{table_name}.{fk_col} = {ref}",
                            }
                        )

        return join_paths

    def find_entity_in_schema(self, entity: str) -> List[Dict[str, str]]:
        """
        查找与给定实体相关的 schema 元素（表/列）。
        使用精确匹配、大小写不敏感匹配和部分匹配。
        """
        entity_lower = entity.lower().replace("_", " ")
        matches = []

        for table in self.tables:
            # 匹配表名
            table_name_lower = table.table_name.lower().replace("_", " ")
            if entity_lower in table_name_lower or table_name_lower in entity_lower:
                matches.append(
                    {
                        "type": "table",
                        "name": self._table_key(table),
                        "relevance": "high",
                    }
                )

            # 匹配列名
            for col in table.columns:
                col_name_lower = col.name.lower().replace("_", " ")
                if entity_lower in col_name_lower or col_name_lower in entity_lower:
                    matches.append(
                        {
                            "type": "column",
                            "table": self._table_key(table),
                            "name": col.name,
                            "description": col.description or "",
                            "relevance": "medium",
                        }
                    )

        return matches

    def get_join_graph_summary(self) -> str:
        """获取所有关系摘要，供 Agent prompt 使用"""
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

    def find_join_path_between_tables(self, table_a: str, table_b: str) -> Optional[List[str]]:
        """
        在两张表之间通过 BFS 查找基于外键的 JOIN 路径。
        返回表名路径。
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
