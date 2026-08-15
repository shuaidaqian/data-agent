"""基于 sqlglot AST 的 SQL 安全校验器。"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import sqlglot
from sqlglot import exp

from sql_agent.core.types import TableDescription
from sql_agent.security.policy import SQLSafetyPolicy
from sql_agent.security.types import (
    SQLRiskLevel,
    SQLSafetyReport,
    SQLSafetyViolation,
    SQLViolationType,
)


class SQLSafetyValidator:
    """使用 AST 校验 SQL 是否只访问允许的表和列。"""

    def __init__(
        self,
        table_descriptions: List[TableDescription],
        policy: SQLSafetyPolicy | None = None,
        dialect: str = "sqlite",
    ):
        self.table_descriptions = table_descriptions
        self.policy = policy or SQLSafetyPolicy()
        self.dialect = dialect or "sqlite"
        self._tables = self._build_table_index(table_descriptions)

    def validate(self, sql: str) -> SQLSafetyReport:
        sql = (sql or "").strip().rstrip(";")
        violations: List[SQLSafetyViolation] = []

        try:
            expressions = sqlglot.parse(sql, read=self.dialect)
        except Exception as exc:
            return self._blocked(
                sql,
                [
                    SQLSafetyViolation(
                        type=SQLViolationType.PARSE_ERROR.value,
                        message=f"SQL 解析失败：{exc}",
                    )
                ],
            )

        if len(expressions) != 1:
            return self._blocked(
                sql,
                [
                    SQLSafetyViolation(
                        type=SQLViolationType.MULTI_STATEMENT.value,
                        message="不允许执行多语句 SQL。",
                    )
                ],
            )

        expression = expressions[0]
        if self.policy.allow_select_only and not isinstance(expression, exp.Select):
            return self._blocked(
                sql,
                [
                    SQLSafetyViolation(
                        type=SQLViolationType.NON_SELECT_STATEMENT.value,
                        message="只允许执行 SELECT 查询。",
                    )
                ],
            )

        if expression.args.get("with") and not self.policy.allow_cte:
            violations.append(
                SQLSafetyViolation(
                    type=SQLViolationType.CTE_NOT_ALLOWED.value,
                    message="当前策略不允许 CTE。",
                )
            )

        if not self.policy.allow_subquery and list(expression.find_all(exp.Subquery)):
            violations.append(
                SQLSafetyViolation(
                    type=SQLViolationType.SUBQUERY_NOT_ALLOWED.value,
                    message="当前策略不允许子查询。",
                )
            )

        cte_names = self._cte_names(expression)
        table_aliases: Dict[str, str] = {}
        referenced_tables: Set[str] = set()
        for table_expr in expression.find_all(exp.Table):
            table_name = self._table_expression_name(table_expr)
            normalized_table = self._normalize_identifier(table_name)
            if normalized_table in cte_names:
                table_aliases[self._normalize_identifier(table_expr.alias_or_name)] = (
                    normalized_table
                )
                continue

            resolved_table = self._resolve_table(table_name)
            if not resolved_table:
                violations.append(
                    SQLSafetyViolation(
                        type=SQLViolationType.UNKNOWN_TABLE.value,
                        message=f"表 `{table_name}` 不在允许的 schema 白名单中。",
                        identifier=table_name,
                        table=table_name,
                    )
                )
                continue

            referenced_tables.add(resolved_table)
            table_aliases[self._normalize_identifier(table_expr.alias_or_name)] = resolved_table
            table_aliases[self._normalize_identifier(table_expr.name)] = resolved_table

        if self.policy.max_joins is not None:
            join_count = len(list(expression.find_all(exp.Join)))
            if join_count > self.policy.max_joins:
                violations.append(
                    SQLSafetyViolation(
                        type=SQLViolationType.UNSUPPORTED_SQL.value,
                        message=f"JOIN 数量 {join_count} 超过策略限制 {self.policy.max_joins}。",
                    )
                )

        if not self.policy.allow_select_star and self._has_projection_star(expression):
            violations.append(
                SQLSafetyViolation(
                    type=SQLViolationType.STAR_NOT_ALLOWED.value,
                    message="当前策略不允许 SELECT *。",
                    identifier="*",
                )
            )

        table_scopes = self._build_select_table_scopes(expression, cte_names)
        columns = self._validate_columns(
            expression,
            table_aliases,
            referenced_tables,
            cte_names,
            table_scopes,
        )
        violations.extend(columns["violations"])
        violations.extend(self._validate_functions(expression))

        report = SQLSafetyReport(
            allowed=not violations,
            risk_level=SQLRiskLevel.LOW.value if not violations else SQLRiskLevel.BLOCKED.value,
            sql=sql,
            normalized_sql=expression.sql(dialect=self.dialect),
            tables=sorted(referenced_tables),
            columns=sorted(columns["columns"]),
            violations=violations,
        )
        return report

    def _validate_columns(
        self,
        expression: exp.Expression,
        table_aliases: Dict[str, str],
        referenced_tables: Set[str],
        cte_names: Set[str],
        table_scopes: Dict[int, Set[str]],
    ) -> Dict[str, object]:
        resolved_columns: Set[str] = set()
        violations: List[SQLSafetyViolation] = []
        for column_expr in expression.find_all(exp.Column):
            column_name = column_expr.name
            table_ref = self._normalize_identifier(column_expr.table or "")
            if self._is_cte_column(column_expr, cte_names, table_aliases):
                continue

            if table_ref:
                table_name = table_aliases.get(table_ref)
                if not table_name:
                    violations.append(
                        SQLSafetyViolation(
                            type=SQLViolationType.UNKNOWN_TABLE.value,
                            message=f"列 `{column_expr.sql()}` 引用了未知表或别名 `{column_expr.table}`。",
                            identifier=column_expr.sql(),
                            table=column_expr.table,
                            column=column_name,
                        )
                    )
                    continue
                if not self._has_column(table_name, column_name):
                    violations.append(
                        SQLSafetyViolation(
                            type=SQLViolationType.UNKNOWN_COLUMN.value,
                            message=f"列 `{column_name}` 不在表 `{table_name}` 白名单中。",
                            identifier=column_expr.sql(),
                            table=table_name,
                            column=column_name,
                        )
                    )
                    continue
                resolved_columns.add(f"{table_name}.{column_name}")
                continue

            nearest_select = self._nearest_select(column_expr)
            scope_tables = (
                table_scopes.get(id(nearest_select), set())
                if nearest_select is not None
                else referenced_tables
            )
            if nearest_select is not None and not scope_tables:
                continue
            candidate_tables = [
                table_name
                for table_name in scope_tables
                if self._has_column(table_name, column_name)
            ]
            if len(candidate_tables) == 1:
                resolved_columns.add(f"{candidate_tables[0]}.{column_name}")
            elif len(candidate_tables) > 1:
                violations.append(
                    SQLSafetyViolation(
                        type=SQLViolationType.AMBIGUOUS_COLUMN.value,
                        message=f"列 `{column_name}` 在多张表中存在，请使用表名或别名限定。",
                        identifier=column_name,
                        column=column_name,
                    )
                )
            elif not referenced_tables:
                continue
            else:
                violations.append(
                    SQLSafetyViolation(
                        type=SQLViolationType.UNKNOWN_COLUMN.value,
                        message=f"列 `{column_name}` 不在允许的表白名单中。",
                        identifier=column_name,
                        column=column_name,
                    )
                )
        return {"columns": resolved_columns, "violations": violations}

    def _validate_functions(self, expression: exp.Expression) -> List[SQLSafetyViolation]:
        violations: List[SQLSafetyViolation] = []
        denied = {name.lower() for name in self.policy.denied_functions}
        allowed = (
            {name.lower() for name in self.policy.allowed_functions}
            if self.policy.allowed_functions
            else None
        )
        for func in expression.find_all(exp.Func):
            func_name = (func.sql_name() or "").lower()
            if func_name in denied or (allowed is not None and func_name not in allowed):
                violations.append(
                    SQLSafetyViolation(
                        type=SQLViolationType.FUNCTION_NOT_ALLOWED.value,
                        message=f"当前策略不允许函数 `{func_name}`。",
                        identifier=func_name,
                    )
                )
        return violations

    def _has_projection_star(self, expression: exp.Expression) -> bool:
        for star_expr in expression.find_all(exp.Star):
            if not self._is_function_argument(star_expr):
                return True
        return False

    def _is_function_argument(self, expression: exp.Expression) -> bool:
        current = getattr(expression, "parent", None)
        while current is not None:
            if isinstance(current, exp.Func):
                return True
            if isinstance(current, exp.Select):
                return False
            current = getattr(current, "parent", None)
        return False

    def _is_cte_column(
        self,
        column_expr: exp.Column,
        cte_names: Set[str],
        table_aliases: Dict[str, str],
    ) -> bool:
        table_ref = self._normalize_identifier(column_expr.table or "")
        return bool(table_ref and table_aliases.get(table_ref) in cte_names)

    def _build_select_table_scopes(
        self,
        expression: exp.Expression,
        cte_names: Set[str],
    ) -> Dict[int, Set[str]]:
        scopes: Dict[int, Set[str]] = {}
        for table_expr in expression.find_all(exp.Table):
            table_name = self._table_expression_name(table_expr)
            normalized_table = self._normalize_identifier(table_name)
            if normalized_table in cte_names:
                continue
            resolved_table = self._resolve_table(table_name)
            nearest_select = self._nearest_select(table_expr)
            if resolved_table and nearest_select is not None:
                scopes.setdefault(id(nearest_select), set()).add(resolved_table)
        return scopes

    def _nearest_select(self, expression: exp.Expression) -> Optional[exp.Select]:
        current = expression
        while current is not None:
            if isinstance(current, exp.Select):
                return current
            current = getattr(current, "parent", None)
        return None

    def _cte_names(self, expression: exp.Expression) -> Set[str]:
        return {
            self._normalize_identifier(cte.alias_or_name)
            for cte in expression.find_all(exp.CTE)
            if cte.alias_or_name
        }

    def _table_expression_name(self, table_expr: exp.Table) -> str:
        name = table_expr.name
        db = table_expr.args.get("db")
        if db:
            return f"{db}.{name}"
        return name

    def _resolve_table(self, table_name: str) -> Optional[str]:
        normalized = self._normalize_identifier(table_name)
        if self.policy.allowed_schemas and "." in normalized:
            schema = normalized.split(".", 1)[0]
            if schema not in {
                self._normalize_identifier(item) for item in self.policy.allowed_schemas
            }:
                return None
        if normalized not in self._tables:
            return None
        return normalized

    def _has_column(self, table_name: str, column_name: str) -> bool:
        table = self._tables.get(self._normalize_identifier(table_name))
        if not table:
            return False
        normalized_column = self._normalize_identifier(column_name)
        return any(
            self._normalize_identifier(column.name) == normalized_column for column in table.columns
        )

    def _build_table_index(
        self, table_descriptions: List[TableDescription]
    ) -> Dict[str, TableDescription]:
        index = {}
        for table in table_descriptions:
            names = [table.table_name]
            if table.schema_name:
                names.append(f"{table.schema_name}.{table.table_name}")
            for name in names:
                index[self._normalize_identifier(name)] = table
        return index

    def _blocked(self, sql: str, violations: List[SQLSafetyViolation]) -> SQLSafetyReport:
        return SQLSafetyReport(
            allowed=False,
            risk_level=SQLRiskLevel.BLOCKED.value,
            sql=sql,
            normalized_sql="",
            tables=[],
            columns=[],
            violations=violations,
        )

    def _normalize_identifier(self, value: str) -> str:
        return str(value).strip().strip('"`[]').lower()
