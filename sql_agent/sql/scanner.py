"""
数据库 schema 扫描器。

发现表结构、列、类型和关系。
基于 Dataherald 的 db_scanner 模块改造。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import inspect
from sqlalchemy import text as sa_text

from sql_agent.core.types import ColumnMetadata, TableDescription
from sql_agent.sql.database import SQLDatabase

logger = logging.getLogger(__name__)


class SchemaScanner:
    """扫描数据库 schema 并构建 TableDescription 对象"""

    def __init__(self, database: SQLDatabase):
        self.database = database
        self._inspector = inspect(database._engine)

    def scan_all_tables(self, db_connection_id: str) -> List[TableDescription]:
        """扫描数据库中的所有表和视图"""
        tables = []
        for schema_name in self._inspector.get_schema_names():
            for table_name in self._inspector.get_table_names(schema=schema_name):
                td = self._scan_table(db_connection_id, table_name, schema_name)
                tables.append(td)
            for view_name in self._inspector.get_view_names(schema=schema_name):
                td = self._scan_table(db_connection_id, view_name, schema_name)
                tables.append(td)
        return tables

    def scan_tables(self, db_connection_id: str, table_names: List[str]) -> List[TableDescription]:
        """扫描指定表"""
        result = []
        for full_name in table_names:
            parts = full_name.split(".")
            if len(parts) == 2:
                schema, table = parts
            else:
                schema, table = None, parts[0]
            td = self._scan_table(db_connection_id, table, schema)
            if td:
                result.append(td)
        return result

    def _scan_table(
        self, db_connection_id: str, table_name: str, schema_name: Optional[str] = None
    ) -> Optional[TableDescription]:
        """扫描单张表"""
        try:
            cols = self._inspector.get_columns(table_name, schema=schema_name)
            pk_constraint = self._inspector.get_pk_constraint(table_name, schema=schema_name)
            fk_constraints = self._inspector.get_foreign_keys(table_name, schema=schema_name)
            pk_columns = set(pk_constraint.get("constrained_columns", []))

            # 构建外键查找表
            fk_map = {}
            for fk in fk_constraints:
                for col, ref_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                    fk_map[col] = f"{fk['referred_schema']}.{fk['referred_table']}.{ref_col}"

            columns = []
            for col in cols:
                col_name = col["name"]
                columns.append(
                    ColumnMetadata(
                        name=col_name,
                        data_type=str(col["type"]),
                        is_primary_key=col_name in pk_columns,
                        is_foreign_key=col_name in fk_map,
                        foreign_key_ref=fk_map.get(col_name),
                    )
                )

            full_name = f"{schema_name}.{table_name}" if schema_name else table_name
            row_count = self._row_count(full_name)
            self._apply_column_samples(full_name, columns)
            self._apply_column_statistics(full_name, columns)
            self._apply_column_semantics(columns)

            # 构建类似 DDL 的表结构文本
            table_schema = (
                f"CREATE TABLE {schema_name + '.' if schema_name else ''}{table_name} (\n"
            )
            col_defs = []
            for col in columns:
                nullable = "" if col.is_primary_key else " NULL"
                col_defs.append(f"  {col.name} {col.data_type}{nullable}")
            if pk_columns:
                col_defs.append(f"  PRIMARY KEY ({', '.join(pk_columns)})")
            for fk in fk_constraints:
                col_defs.append(
                    f"  FOREIGN KEY ({', '.join(fk['constrained_columns'])}) "
                    f"REFERENCES {fk['referred_table']} ({', '.join(fk['referred_columns'])})"
                )
            table_schema += ",\n".join(col_defs) + "\n)"
            sample_context = self._build_sample_context(columns)
            if sample_context:
                table_schema += "\n" + sample_context

            return TableDescription(
                table_name=table_name,
                schema_name=schema_name,
                db_connection_id=db_connection_id,
                columns=columns,
                table_schema=table_schema,
                row_count=row_count,
                status="SCANNED",
            )
        except Exception as e:
            logger.warning(f"Failed to scan {schema_name}.{table_name}: {e}")
            return None

    def _sample_rows(
        self, full_name: str, columns: List[ColumnMetadata], limit: int = 3
    ) -> List[str]:
        """获取表的样本行"""
        try:
            with self.database._engine.connect() as conn:
                result = conn.execute(
                    sa_text(f"SELECT * FROM {self._quote_table(full_name)} LIMIT :limit"),
                    {"limit": limit},
                )
                return [str(dict(row._mapping)) for row in result.fetchall()]
        except Exception:
            return []

    def _apply_column_samples(
        self, full_name: str, columns: List[ColumnMetadata], limit: int = 20
    ) -> None:
        """采集样本值和简单列上下文"""
        table_ref = self._quote_table(full_name)
        with self.database._engine.connect() as conn:
            for column in columns:
                try:
                    column_ref = self._quote_identifier(column.name)
                    result = conn.execute(
                        sa_text(
                            f"SELECT DISTINCT {column_ref} AS value "
                            f"FROM {table_ref} "
                            f"WHERE {column_ref} IS NOT NULL "
                            f"LIMIT :limit"
                        ),
                        {"limit": limit},
                    )
                    values = []
                    for row in result.fetchall():
                        value = row._mapping["value"]
                        if value is not None:
                            values.append(str(value))
                    column.sample_values = values[:5] or None
                    if values and len(values) <= limit:
                        column.low_cardinality = True
                        column.categories = values
                except Exception as e:
                    logger.debug(f"Failed to sample {full_name}.{column.name}: {e}")

    def _apply_column_statistics(self, full_name: str, columns: List[ColumnMetadata]) -> None:
        """采集列级统计信息，用于后续排序和解释。"""
        table_ref = self._quote_table(full_name)
        with self.database._engine.connect() as conn:
            for column in columns:
                try:
                    column_ref = self._quote_identifier(column.name)
                    result = conn.execute(
                        sa_text(
                            f"SELECT "
                            f"COUNT(DISTINCT {column_ref}) AS distinct_count, "
                            f"SUM(CASE WHEN {column_ref} IS NULL THEN 1 ELSE 0 END) AS null_count "
                            f"FROM {table_ref}"
                        )
                    )
                    row = result.fetchone()
                    if row:
                        column.distinct_count = int(row._mapping["distinct_count"] or 0)
                        column.null_count = int(row._mapping["null_count"] or 0)
                except Exception as e:
                    logger.debug(f"Failed to profile {full_name}.{column.name}: {e}")

    def _apply_column_semantics(self, columns: List[ColumnMetadata]) -> None:
        """基于列名、类型和关系生成轻量语义标签。"""
        for column in columns:
            semantic_type, synonyms = self._infer_column_semantics(column)
            column.semantic_type = semantic_type
            column.synonyms = synonyms

    def _infer_column_semantics(self, column: ColumnMetadata) -> tuple[str, List[str]]:
        name = column.name.lower()
        data_type = column.data_type.lower()
        synonyms = []

        if column.is_foreign_key:
            synonyms.extend(["关联键", "外键", "引用"])
            return "foreign_key", synonyms
        if column.is_primary_key or name == "id" or name.endswith("_id"):
            synonyms.extend(["标识", "编号", "主键"])
            return "identifier", synonyms
        if "date" in name or "time" in name or any(t in data_type for t in ["date", "time"]):
            synonyms.extend(["日期", "时间"])
            return "date", synonyms
        if any(
            token in name for token in ["amount", "price", "salary", "quantity", "total", "count"]
        ):
            synonyms.extend(["数值", "指标", "金额"])
            return "measure", synonyms
        if any(token in name for token in ["name", "title", "label"]):
            synonyms.extend(["名称", "名字", "文本"])
            return "name", synonyms
        if column.low_cardinality or any(token in name for token in ["status", "category", "type"]):
            synonyms.extend(["分类", "枚举", "状态"])
            return "category", synonyms
        if any(t in data_type for t in ["int", "float", "numeric", "decimal", "real"]):
            synonyms.extend(["数值", "指标"])
            return "measure", synonyms
        synonyms.append("文本")
        return "text", synonyms

    def _row_count(self, full_name: str) -> Optional[int]:
        try:
            with self.database._engine.connect() as conn:
                result = conn.execute(
                    sa_text(f"SELECT COUNT(*) AS cnt FROM {self._quote_table(full_name)}")
                )
                return int(result.scalar() or 0)
        except Exception:
            return None

    def _build_sample_context(self, columns: List[ColumnMetadata]) -> str:
        lines = []
        for column in columns:
            if column.sample_values:
                values = ", ".join(column.sample_values)
                lines.append(f"/* Column `{column.name}` sample values: {values} */")
            if column.semantic_type:
                lines.append(
                    f"/* Column `{column.name}` semantic type: {column.semantic_type}; "
                    f"synonyms: {', '.join(column.synonyms)} */"
                )
        return "\n".join(lines)

    def _quote_table(self, full_name: str) -> str:
        return ".".join(self._quote_identifier(part) for part in full_name.split("."))

    def _quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
