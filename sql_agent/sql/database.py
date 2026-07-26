"""
SQL 数据库抽象层。
基于 Dataherald 的 sql_database/base.py 改造，并增强类型安全。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from sql_agent.core.types import DatabaseConnection

logger = logging.getLogger(__name__)

SQL_INJECTION_PATTERNS = [
    r"\bDROP\s+TABLE",
    r"\bDROP\s+DATABASE",
    r"\bTRUNCATE\s+TABLE",
    r"\bDELETE\s+FROM",
    r"\bINSERT\s+INTO",
    r"\bUPDATE\s+",
    r"\bALTER\s+TABLE",
    r"\bCREATE\s+TABLE",
    r"\bEXEC\s+",
    r"\bEXECUTE\s+",
]


class SQLInjectionError(Exception):
    pass


class SQLDatabase:
    """SQLAlchemy engine 的封装器"""

    def __init__(self, engine, dialect: str = ""):
        self._engine = engine
        self.dialect = dialect or str(engine.url.get_dialect())

    @staticmethod
    def get_sql_engine(
        database_connection: DatabaseConnection,
        read_only: bool = False,
    ) -> "SQLDatabase":
        """根据数据库连接配置创建 SQLDatabase"""
        uri = database_connection.connection_uri
        if read_only:
            engine = create_engine(
                uri, connect_args={"options": "-c default_transaction_read_only=on"}
            )
        else:
            engine = create_engine(uri)
        return SQLDatabase(engine)

    def get_tables_and_views(self) -> List[str]:
        """获取所有表和视图名称"""
        inspector = inspect(self._engine)
        schemas = inspector.get_schema_names()
        tables = []
        for schema in schemas:
            tables.extend(
                f"{schema}.{t}" if schema != "public" else t
                for t in inspector.get_table_names(schema=schema)
            )
            tables.extend(
                f"{schema}.{v}" if schema != "public" else v
                for v in inspector.get_view_names(schema=schema)
            )
        return tables

    def run_sql(self, query: str, top_k: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        """执行 SQL 查询并返回结果"""
        query = self.parser_to_filter_commands(query)
        with self._engine.connect() as connection:
            result = connection.execute(text(query))
            if top_k:
                rows = result.fetchmany(top_k)
            else:
                rows = result.fetchall()

            columns = list(result.keys())
            data = [dict(zip(columns, row)) for row in rows]

            return query, {"result": data, "columns": columns, "row_count": len(data)}

    def parser_to_filter_commands(self, query: str) -> str:
        """过滤危险 SQL 命令"""
        query_upper = query.upper().strip()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, query_upper, re.IGNORECASE):
                raise SQLInjectionError(f"Dangerous SQL pattern detected: {pattern}")
        return query

    def get_table_ddl(self, table_name: str) -> str:
        """获取指定表的 CREATE TABLE 语句"""
        inspector = inspect(self._engine)
        try:
            columns = inspector.get_columns(table_name)
            pk = inspector.get_pk_constraint(table_name)
            fks = inspector.get_foreign_keys(table_name)
        except SQLAlchemyError:
            return ""

        col_defs = []
        for col in columns:
            col_type = str(col["type"])
            nullable = "" if col.get("nullable", True) else " NOT NULL"
            default = f" DEFAULT {col['default']}" if col.get("default") else ""
            col_defs.append(f"  {col['name']} {col_type}{nullable}{default}")

        # 主键
        if pk.get("constrained_columns"):
            col_defs.append(f"  PRIMARY KEY ({', '.join(pk['constrained_columns'])})")

        # 外键
        for fk in fks:
            col_defs.append(
                f"  FOREIGN KEY ({', '.join(fk['constrained_columns'])}) "
                f"REFERENCES {fk['referred_table']} "
                f"({', '.join(fk['referred_columns'])})"
            )

        return f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);"
