"""
Agent 工具定义。

这些工具让 NL-to-SQL Agent 能够与数据库交互。
每个工具都是带有独立提示描述的自包含函数。
相比 Dataherald，这些工具与 LangChain 的 toolkit 模式解耦。
"""

from __future__ import annotations

import datetime
import difflib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from sqlalchemy import text as sa_text

from sql_agent.core.types import (
    TableDescription,
)
from sql_agent.llm.base import LLMBackend
from sql_agent.security import SQLSafetyValidator
from sql_agent.sql.database import SQLDatabase

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 50
TOP_TABLES = 20


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool = True
    output: str = ""
    error: Optional[str] = None


@dataclass
class ToolDef:
    """Agent 可用工具定义"""

    name: str
    description: str
    fn: Callable[..., ToolResult]
    parameters: Dict[str, str] = field(default_factory=dict)


class AgentToolkit:
    """
    SQL Agent 可用工具集合。
    与 LangChain 解耦，直接使用原生 Python 可调用对象。
    """

    def __init__(
        self,
        database: SQLDatabase,
        db_scan: List[TableDescription],
        llm_backend: LLMBackend,
        few_shot_examples: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[List[Dict[str, str]]] = None,
        is_multiple_schema: bool = False,
    ):
        self.database = database
        self.db_scan = db_scan
        self.llm_backend = llm_backend
        self.few_shot_examples = few_shot_examples
        self.instructions = instructions
        self.is_multiple_schema = is_multiple_schema
        self._allowed_tables = self._build_schema_index()
        self._sql_safety_validator = SQLSafetyValidator(
            table_descriptions=db_scan,
            dialect=self.database.dialect,
        )

    def get_tools(self) -> List[ToolDef]:
        """返回可用工具列表"""
        tools = [
            ToolDef(
                name="SqlDbQuery",
                description="Execute a SQL query and return results. Input: a well-formed SQL query.",
                fn=self._execute_query,
            ),
            ToolDef(
                name="SystemTime",
                description="Get current date and time. Use this if the question involves time or date.",
                fn=self._get_system_time,
            ),
            ToolDef(
                name="DbTablesWithRelevanceScores",
                description="Find tables relevant to the user question using embedding similarity.",
                fn=self._find_relevant_tables,
            ),
            ToolDef(
                name="DbRelevantTablesSchema",
                description="Get schema (columns, types) for given tables. Input: comma-separated table names.",
                fn=self._get_table_schema,
            ),
            ToolDef(
                name="DbColumnEntityChecker",
                description="Check if an entity exists in a column. Input format: table_name -> column_name, entity",
                fn=self._check_entity,
            ),
            ToolDef(
                name="DbRelevantColumnsInfo",
                description="Get descriptions and sample values for specific columns. Input: table1 -> col1, table1 -> col2",
                fn=self._get_column_info,
            ),
        ]

        if self.few_shot_examples:
            tools.append(
                ToolDef(
                    name="FewshotExamplesRetriever",
                    description="Retrieve similar question-SQL pairs as examples. Input: number of examples needed.",
                    fn=self._get_few_shot_examples,
                )
            )

        if self.instructions:
            tools.append(
                ToolDef(
                    name="GetAdminInstructions",
                    description="Get admin-defined SQL generation rules and instructions.",
                    fn=self._get_instructions,
                )
            )

        return tools

    def _execute_query(self, query: str, top_k: int = DEFAULT_TOP_K) -> ToolResult:
        """执行 SQL 查询并返回结果"""
        try:
            if "```sql" in query:
                query = query.replace("```sql", "").replace("```", "")
            query = query.strip().rstrip(";")
            validation = self._validate_sql_query(query)
            if validation:
                return validation
            result = self.database.run_sql(query, top_k)
            return ToolResult(output=str(result))
        except Exception as e:
            return ToolResult(success=False, output=f"Error: {str(e)}")

    def _get_system_time(self, tool_input: str = "") -> ToolResult:
        """获取当前系统时间"""
        now = datetime.datetime.now()
        return ToolResult(output=f"Current Date and Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    def _find_relevant_tables(self, user_question: str) -> ToolResult:
        """通过 embedding 相似度查找与用户问题相关的表"""
        try:
            question_embedding = self.llm_backend.embed([user_question])[0]
            table_representations = []
            for table in self.db_scan:
                col_rep = ", ".join(
                    f"{c.name}: {c.description}" if c.description else c.name for c in table.columns
                )
                desc = (
                    f"Table {table.table_name} has: {table.description}"
                    if table.description
                    else ""
                )
                rep = f"Table {table.table_name}: [{col_rep}]. {desc}"
                table_representations.append((table.schema_name, table.table_name, rep))

            # 计算 embedding 和相似度
            docs_embeddings = self.llm_backend.embed([r[2] for r in table_representations])
            similarities = [
                float(
                    np.dot(question_embedding, de)
                    / (np.linalg.norm(question_embedding) * np.linalg.norm(de))
                )
                for de in docs_embeddings
            ]

            # 排序并取 top_k
            ranked = sorted(
                zip(table_representations, similarities), key=lambda x: x[1], reverse=True
            )[:TOP_TABLES]

            result = ""
            for (schema, table_name, _), score in ranked:
                full_name = f"{schema}.{table_name}" if schema else table_name
                result += f"Table: `{full_name}`, relevance: {score:.4f}\n"
            return ToolResult(output=result)
        except Exception as e:
            return ToolResult(success=False, output=f"Error: {str(e)}")

    def _get_table_schema(self, table_names: str) -> ToolResult:
        """获取指定表的 schema"""
        try:
            names = [n.strip() for n in table_names.split(",")]
            tables = []
            for name in names:
                table = self._find_table(name)
                if not table:
                    return self._schema_denied("表", name)
                tables.append(table)
            result = "```sql\n"
            for table in tables:
                result += table.table_schema + "\n"
                if table.description:
                    full_name = self._full_table_name(table)
                    result += f"/* Table `{full_name}`: {table.description} */\n"
                for col in table.columns:
                    if col.description:
                        result += f"/* Column `{col.name}`: {col.description} */\n"
            result += "```\n"
            return ToolResult(output=result)
        except Exception as e:
            return ToolResult(success=False, output=f"Error: {str(e)}")

    def _check_entity(self, tool_input: str) -> ToolResult:
        """检查实体值是否存在于指定列中"""
        try:
            schema_part, entity = tool_input.rsplit(",", 1)
            entity = entity.strip()
            if "->" in schema_part:
                table_name, column_name = schema_part.split("->")
            else:
                return ToolResult(
                    success=False, output="Invalid format. Use: table_name -> column_name, entity"
                )

            table_name = table_name.strip()
            column_name = column_name.strip()
            table = self._find_table(table_name)
            if not table:
                return self._schema_denied("表", table_name)
            if not self._has_column(table, column_name):
                return self._schema_denied("列", f"{table_name}.{column_name}")
            table_name = self._full_table_name(table)

            # 先尝试 LIKE 匹配，再对所有去重值做模糊匹配
            try:
                search = f"%{entity.lower()}%"
                query = f"SELECT DISTINCT {column_name} FROM {table_name} WHERE LOWER({column_name}) LIKE :pat"
                with self.database._engine.connect() as conn:
                    result = conn.execute(sa_text(query), {"pat": search}).fetchmany(25)
                exact_matches = [str(r[0]) for r in result]
            except Exception:
                exact_matches = []

            # 对完整去重值进行模糊匹配
            try:
                query = f"SELECT DISTINCT {column_name} FROM {table_name}"
                with self.database._engine.connect() as conn:
                    all_vals = conn.execute(sa_text(query)).fetchall()
                fuzzy_matches = []
                for v in all_vals:
                    val_str = str(v[0]).strip()
                    ratio = difflib.SequenceMatcher(None, val_str.lower(), entity.lower()).ratio()
                    if ratio >= 0.4:
                        fuzzy_matches.append((val_str, ratio))
                fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                fuzzy_matches = fuzzy_matches[:25]
            except Exception:
                fuzzy_matches = []

            result = "Similar values:\n"
            seen = set()
            for item in exact_matches:
                if item not in seen:
                    result += f"  {item}\n"
                    seen.add(item)
            for item, _ in fuzzy_matches:
                if item not in seen:
                    result += f"  {item}\n"
                    seen.add(item)

            return ToolResult(output=result)
        except Exception as e:
            return ToolResult(success=False, output=f"Error: {str(e)}")

    def _get_column_info(self, column_names: str) -> ToolResult:
        """获取列级信息"""
        try:
            items = column_names.split(", ")
            result = ""
            for item in items:
                if "->" not in item:
                    return ToolResult(
                        success=False, output=f"Invalid format: {item}. Use: table -> column"
                    )
                table_name, col_name = item.split("->")
                table_name = table_name.strip()
                col_name = col_name.strip()

                table = self._find_table(table_name)
                if not table:
                    return self._schema_denied("表", table_name)
                col = self._find_column(table, col_name)
                if not col:
                    return self._schema_denied("列", f"{table_name}.{col_name}")
                full_name = self._full_table_name(table)
                result += f"Table: {full_name}, Column: {col_name}\n"
                if col.description:
                    result += f"  Description: {col.description}\n"
                if col.low_cardinality and col.categories:
                    result += f"  Categories: {', '.join(col.categories[:20])}\n"
                if col.sample_values:
                    result += f"  Sample values: {', '.join(col.sample_values[:5])}\n"
            return ToolResult(output=result)
        except Exception as e:
            return ToolResult(success=False, output=f"Error: {str(e)}")

    def _get_few_shot_examples(self, number_of_samples: str) -> ToolResult:
        """检索 few-shot 示例"""
        try:
            n = int(number_of_samples.strip())
        except ValueError:
            return ToolResult(success=False, output="Input should be an integer")

        if not self.few_shot_examples:
            return ToolResult(output="No examples available")

        result = ""
        for example in self.few_shot_examples[:n]:
            result += f"Question: {example.get('prompt_text', '')}\n"
            result += f"```sql\n{example.get('sql', '')}\n```\n"
        return ToolResult(output=result)

    def _get_instructions(self, tool_input: str = "") -> ToolResult:
        """获取管理员指令"""
        if not self.instructions:
            return ToolResult(output="No instructions available")
        result = "Admin instructions (MUST follow these):\n"
        for i, inst in enumerate(self.instructions, 1):
            result += f"{i}. {inst.get('instruction', '')}\n"
        return ToolResult(output=result)

    def _build_schema_index(self) -> Dict[str, TableDescription]:
        index = {}
        for table in self.db_scan:
            names = {table.table_name, self._full_table_name(table)}
            for name in names:
                index[self._normalize_identifier(name)] = table
        return index

    def _normalize_identifier(self, value: str) -> str:
        return value.strip().strip('"`[]').lower()

    def _full_table_name(self, table: TableDescription) -> str:
        return f"{table.schema_name}.{table.table_name}" if table.schema_name else table.table_name

    def _find_table(self, table_name: str) -> Optional[TableDescription]:
        return self._allowed_tables.get(self._normalize_identifier(table_name))

    def _find_column(self, table: TableDescription, column_name: str):
        normalized = self._normalize_identifier(column_name.split(".")[-1])
        for column in table.columns:
            if self._normalize_identifier(column.name) == normalized:
                return column
        return None

    def _has_column(self, table: TableDescription, column_name: str) -> bool:
        return self._find_column(table, column_name) is not None

    def _schema_denied(self, kind: str, name: str) -> ToolResult:
        return ToolResult(
            success=False,
            output=f"{kind} `{name}` 不在允许的 schema 白名单中",
        )

    def _validate_sql_query(self, query: str) -> Optional[ToolResult]:
        safety_report = self._sql_safety_validator.validate(query)
        if not safety_report.allowed:
            return ToolResult(success=False, output=safety_report.to_message())
        return None
