"""候选 SQL 执行、校验、评分和排序。"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from sql_agent.core.types import TableDescription
from sql_agent.ranking.candidate import CandidateExecution, SQLCandidate
from sql_agent.sql.database import SQLDatabase


class CandidateRanker:
    """基于 schema 白名单、执行结果和问题意图排序候选 SQL。"""

    def __init__(
        self,
        database: SQLDatabase,
        table_descriptions: List[TableDescription],
        evaluator=None,
    ):
        self.database = database
        self.table_descriptions = table_descriptions
        self.evaluator = evaluator
        self._tables = self._build_table_index(table_descriptions)

    def rank(self, question: str, candidates: Iterable[str], limit: Optional[int] = None) -> List[SQLCandidate]:
        ranked = [self._score_candidate(question, sql) for sql in self._deduplicate(candidates)]
        ranked.sort(key=lambda candidate: candidate.score, reverse=True)
        return ranked[:limit] if limit else ranked

    def _score_candidate(self, question: str, sql: str) -> SQLCandidate:
        candidate = SQLCandidate(sql=sql.strip().rstrip(";"))
        validation_error = self._validate_sql(candidate.sql)
        if validation_error:
            candidate.status = "INVALID"
            candidate.evidence = validation_error
            candidate.score_components["schema"] = -1.0
            candidate.score = 0.0
            return candidate

        try:
            _, result = self.database.run_sql(candidate.sql, top_k=5)
            candidate.status = "VALID"
            candidate.execution = CandidateExecution(
                success=True,
                row_count=int(result.get("row_count", 0)),
                columns=list(result.get("columns", [])),
                preview=list(result.get("result", []))[:3],
            )
        except Exception as exc:
            candidate.status = "INVALID"
            candidate.execution = CandidateExecution(success=False, error=str(exc))
            candidate.evidence = f"执行失败：{exc}"
            candidate.score_components["execution"] = -1.0
            candidate.score = 0.0
            return candidate

        candidate.score_components = self._score_components(question, candidate.sql)
        candidate.score = round(sum(candidate.score_components.values()), 4)
        candidate.evidence = self._build_evidence(candidate)
        return candidate

    def _score_components(self, question: str, sql: str) -> Dict[str, float]:
        components = {
            "schema": 0.25,
            "execution": 0.25,
            "structure": 0.15,
        }
        if self.evaluator:
            try:
                components["evaluator"] = float(self.evaluator.evaluate(sql, question)) * 0.2
            except Exception:
                components["evaluator"] = 0.0

        intent_bonus = self._intent_bonus(question, sql)
        if intent_bonus:
            components["intent"] = intent_bonus
        return components

    def _intent_bonus(self, question: str, sql: str) -> float:
        text = question.lower()
        sql_upper = sql.upper()
        wants_count = any(token in text for token in ["数量", "多少", "总数", "count", "how many"])
        if wants_count:
            return 0.25 if "COUNT(" in sql_upper else -0.05

        wants_top = any(token in text for token in ["top", "最高", "最大", "排名", "前"])
        if wants_top:
            bonus = 0.0
            if "ORDER BY" in sql_upper:
                bonus += 0.12
            if "LIMIT" in sql_upper or "TOP " in sql_upper:
                bonus += 0.08
            return bonus
        return 0.0

    def _build_evidence(self, candidate: SQLCandidate) -> str:
        columns = ", ".join(candidate.execution.columns) if candidate.execution.columns else "无列信息"
        return (
            f"执行成功，返回 {candidate.execution.row_count} 行；"
            f"结果列：{columns}；"
            f"评分构成：{candidate.score_components}"
        )

    def _validate_sql(self, sql: str) -> Optional[str]:
        try:
            self.database.parser_to_filter_commands(sql)
        except Exception as exc:
            return f"SQL 安全校验失败：{exc}"

        table_names = self._extract_table_names(sql)
        if not table_names:
            return "SQL 未引用任何允许的数据表"

        for table_name in table_names:
            if self._normalize_identifier(table_name) not in self._tables:
                return f"表 `{table_name}` 不在允许的 schema 白名单中"
        return None

    def _extract_table_names(self, sql: str) -> List[str]:
        try:
            from sql_metadata import Parser

            return list(Parser(sql).tables)
        except ModuleNotFoundError:
            return re.findall(
                r"\b(?:FROM|JOIN)\s+([`\"\[]?[\w.]+[`\"\]]?)",
                sql,
                flags=re.IGNORECASE,
            )
        except Exception:
            return []

    def _build_table_index(self, table_descriptions: List[TableDescription]) -> Dict[str, TableDescription]:
        index = {}
        for table in table_descriptions:
            names = [table.table_name]
            if table.schema_name:
                names.append(f"{table.schema_name}.{table.table_name}")
            for name in names:
                index[self._normalize_identifier(name)] = table
        return index

    def _normalize_identifier(self, value: str) -> str:
        return value.strip().strip('"`[]').lower()

    def _deduplicate(self, candidates: Iterable[str]) -> List[str]:
        seen = set()
        output = []
        for sql in candidates:
            clean = sql.strip().rstrip(";")
            normalized = " ".join(clean.split()).lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                output.append(clean)
        return output
