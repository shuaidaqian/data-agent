"""候选 SQL 执行、校验、评分和排序。"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from sql_agent.core.types import TableDescription
from sql_agent.ranking.candidate import (
    CandidateExecution,
    ResultShapeValidation,
    SQLCandidate,
)
from sql_agent.security import SQLSafetyPolicy, SQLSafetyValidator
from sql_agent.sql.database import SQLDatabase


class CandidateRanker:
    """基于 schema 白名单、执行结果和问题意图排序候选 SQL。"""

    def __init__(
        self,
        database: SQLDatabase,
        table_descriptions: List[TableDescription],
        evaluator=None,
        semantic_plan=None,
        verified_sqls: Optional[Iterable[str]] = None,
    ):
        self.database = database
        self.table_descriptions = table_descriptions
        self.evaluator = evaluator
        self.semantic_plan = semantic_plan
        self.verified_sqls = {
            self._normalize_sql(sql) for sql in (verified_sqls or []) if str(sql).strip()
        }
        self._sql_safety_validator = SQLSafetyValidator(
            table_descriptions=table_descriptions,
            policy=SQLSafetyPolicy(allow_select_star=True),
            dialect=self.database.dialect,
        )

    def rank(
        self, question: str, candidates: Iterable[str], limit: Optional[int] = None
    ) -> List[SQLCandidate]:
        ranked = [self._score_candidate(question, sql) for sql in self._deduplicate(candidates)]
        ranked.sort(key=lambda candidate: candidate.score, reverse=True)
        return ranked[:limit] if limit else ranked

    def _score_candidate(self, question: str, sql: str) -> SQLCandidate:
        candidate = SQLCandidate(sql=sql.strip().rstrip(";"))
        normalized_sql = self._normalize_sql(candidate.sql)
        if normalized_sql in self.verified_sqls:
            candidate.source = "verified"
        elif self.semantic_plan and self._matches_semantic_plan(candidate.sql):
            candidate.source = "semantic"
        safety_report = self._validate_sql(candidate.sql)
        candidate.safety = safety_report.to_dict()
        validation_error = None if safety_report.allowed else safety_report.to_message()
        if validation_error:
            candidate.status = "INVALID"
            candidate.evidence = validation_error
            candidate.score_components["schema"] = -1.0
            candidate.score_breakdown = dict(candidate.score_components)
            candidate.selection_reason = validation_error
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
            candidate.score_breakdown = dict(candidate.score_components)
            candidate.selection_reason = candidate.evidence
            candidate.score = 0.0
            return candidate

        candidate.score_components = self._score_components(question, candidate.sql)
        candidate.result_shape = self._validate_result_shape(question, candidate)
        if candidate.result_shape.valid:
            candidate.score_components["result_shape"] = 0.1
        else:
            candidate.score_components["result_shape"] = -0.2
        if normalized_sql in self.verified_sqls:
            candidate.score_components["verified_query"] = 0.35
        if self.semantic_plan and self._matches_semantic_plan(candidate.sql):
            candidate.score_components["semantic_plan_match"] = 0.2
        candidate.score_breakdown = dict(candidate.score_components)
        candidate.score = round(sum(candidate.score_components.values()), 4)
        candidate.selection_reason = self._build_selection_reason(candidate)
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
        columns = (
            ", ".join(candidate.execution.columns) if candidate.execution.columns else "无列信息"
        )
        return (
            f"执行成功，返回 {candidate.execution.row_count} 行；"
            f"结果列：{columns}；"
            f"评分构成：{candidate.score_breakdown}"
        )

    def _build_selection_reason(self, candidate: SQLCandidate) -> str:
        reasons = []
        if candidate.source == "verified":
            reasons.append("命中 verified query")
        elif candidate.source == "semantic":
            reasons.append("匹配语义计划")
        if candidate.execution.success:
            reasons.append(f"真实执行成功，返回 {candidate.execution.row_count} 行")
        if candidate.result_shape.valid:
            reasons.append("结果形状符合问题意图")
        elif candidate.result_shape.reason:
            reasons.append(f"结果形状风险：{candidate.result_shape.reason}")
        return "；".join(reasons) or "基于执行结果和启发式评分排序"

    def _validate_result_shape(
        self, question: str, candidate: SQLCandidate
    ) -> ResultShapeValidation:
        text = question.lower()
        columns = candidate.execution.columns
        numeric_columns = [
            column for column in columns if self._column_is_numeric(candidate, column)
        ]
        grouped_columns = self._extract_group_by_columns(candidate.sql)
        non_numeric_columns = [
            column
            for column in columns
            if column not in numeric_columns or self._column_in_group_by(column, grouped_columns)
        ]
        wants_count = any(token in text for token in ["数量", "多少", "总数", "count", "how many"])
        wants_group = any(token in text for token in ["按", "每", "分组", "各", "group by"])
        wants_trend = any(token in text for token in ["趋势", "按月", "按日", "按年", "trend"])

        if wants_trend:
            has_time = any(self._is_time_like(column) for column in columns)
            if not has_time or not numeric_columns:
                return ResultShapeValidation(
                    valid=False,
                    expected="时间维度 + 数值指标",
                    actual=", ".join(columns),
                    reason="趋势问题需要时间字段和数值指标。",
                )
        if wants_group:
            if not non_numeric_columns or not numeric_columns:
                return ResultShapeValidation(
                    valid=False,
                    expected="维度列 + 指标列",
                    actual=", ".join(columns),
                    reason="分组问题需要同时返回维度列和指标列。",
                )
        elif wants_count:
            if candidate.execution.row_count != 1 or len(numeric_columns) != 1:
                return ResultShapeValidation(
                    valid=False,
                    expected="单行单指标",
                    actual=f"{candidate.execution.row_count} 行，{len(columns)} 列",
                    reason="计数问题更适合返回单行单指标。",
                )
        return ResultShapeValidation(valid=True, expected="符合问题意图", actual=", ".join(columns))

    def _column_is_numeric(self, candidate: SQLCandidate, column: str) -> bool:
        rows = candidate.execution.preview
        if not rows:
            return False
        values = [row.get(column) for row in rows if row.get(column) is not None]
        return bool(values) and all(
            isinstance(value, (int, float)) and not isinstance(value, bool) for value in values
        )

    def _is_time_like(self, column: str) -> bool:
        return any(token in column.lower() for token in ["date", "time", "day", "month", "year"])

    def _extract_group_by_columns(self, sql: str) -> List[str]:
        match = re.search(r"\bGROUP\s+BY\s+(.+?)(?:\bORDER\s+BY\b|\bLIMIT\b|$)", sql, re.IGNORECASE)
        if not match:
            return []
        return [item.strip().strip('"`[]').lower() for item in match.group(1).split(",")]

    def _column_in_group_by(self, column: str, grouped_columns: List[str]) -> bool:
        normalized = column.strip().strip('"`[]').lower()
        return any(
            normalized == item or item.endswith(f".{normalized}") for item in grouped_columns
        )

    def _matches_semantic_plan(self, sql: str) -> bool:
        if not self.semantic_plan:
            return False
        normalized_sql = sql.lower()
        metric_match = all(
            metric.table.lower() in normalized_sql and metric.name.lower() in normalized_sql
            for metric in self.semantic_plan.metrics
        )
        dimension_match = all(
            dimension.column.lower() in normalized_sql or dimension.name.lower() in normalized_sql
            for dimension in self.semantic_plan.dimensions
        )
        return metric_match and dimension_match

    def _validate_sql(self, sql: str):
        report = self._sql_safety_validator.validate(sql)
        if report.allowed and not report.tables:
            report.allowed = False
            report.risk_level = "BLOCKED"
            from sql_agent.security import SQLSafetyViolation, SQLViolationType

            report.violations.append(
                SQLSafetyViolation(
                    type=SQLViolationType.UNSUPPORTED_SQL.value,
                    message="SQL 未引用任何允许的数据表。",
                )
            )
        return report

    def _normalize_sql(self, value: str) -> str:
        return " ".join(value.strip().rstrip(";").split()).lower()

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
