"""基于受控 SQL 执行结果的分析器。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from sql_agent.analysis.types import AnalysisResult, KeyFinding, QueryResultPayload
from sql_agent.ranking.candidate import SQLCandidate


class HeuristicResultAnalyzer:
    """
    启发式结果分析器。

    设计原则：
    1. 答案只能来自 SQL 执行结果，不能使用模型先验编造事实。
    2. 每个关键发现必须带有可追溯 evidence。
    3. 结果不足时明确说明限制，而不是强行下结论。
    """

    def analyze(self, question: str, candidate: SQLCandidate, max_rows: int = 20) -> AnalysisResult:
        result = self._build_result_payload(candidate, max_rows)
        if not candidate.execution.success:
            return AnalysisResult(
                answer="SQL 未成功执行，无法基于数据给出答案。",
                result=result,
                summary=f"候选 SQL 执行失败：{candidate.execution.error or '未知错误'}",
                limitations=["没有可用的 SQL 执行结果，因此不能生成数据结论。"],
                followup_questions=["是否需要查看 SQL 错误并尝试修正？"],
            )

        if result.row_count == 0 or not result.rows:
            return AnalysisResult(
                answer="本次查询没有返回数据。",
                result=result,
                summary="SQL 执行成功，但结果集为空。",
                limitations=[
                    "结果为空可能是筛选条件过窄、数据不存在或当前数据库快照不包含相关记录。",
                    "不能基于空结果推断业务趋势或异常原因。",
                ],
                followup_questions=[
                    "是否需要放宽筛选条件？",
                    "是否需要检查相关表中是否存在对应数据？",
                ],
            )

        if len(result.rows) == 1 and len(result.columns) == 1:
            column = result.columns[0]
            value = result.rows[0].get(column)
            return AnalysisResult(
                answer=f"当前查询结果为 {value}。",
                result=result,
                summary=f"SQL 返回 1 行 1 列，核心指标 `{column}` 的值为 {value}。",
                key_findings=[
                    KeyFinding(
                        claim=f"{column} = {value}",
                        evidence=f"SQL result: {column} = {value}",
                    )
                ],
                limitations=[
                    "该结论仅基于当前数据库快照。",
                    "如果业务口径需要过滤状态、时间范围或权限范围，需要在 SQL 中显式增加条件。",
                ],
                followup_questions=self._suggest_followups(question, result),
            )

        key_findings = self._build_table_findings(result)
        return AnalysisResult(
            answer=f"查询返回 {result.row_count} 行结果，请结合结果明细查看。",
            result=result,
            summary=self._build_summary(result),
            key_findings=key_findings,
            limitations=[
                "该分析只基于返回的结果预览，不代表未返回数据中的完整分布。",
                "如需严格业务结论，应确认统计口径、时间范围和过滤条件。",
            ],
            followup_questions=self._suggest_followups(question, result),
        )

    def _build_result_payload(self, candidate: SQLCandidate, max_rows: int) -> QueryResultPayload:
        preview = list(candidate.execution.preview or [])
        rows = preview[:max_rows]
        return QueryResultPayload(
            columns=list(candidate.execution.columns or []),
            rows=rows,
            row_count=int(candidate.execution.row_count or 0),
            truncated=len(preview) > max_rows,
        )

    def _build_table_findings(self, result: QueryResultPayload) -> List[KeyFinding]:
        findings = []
        if not result.rows:
            return findings

        numeric_columns = [
            column
            for column in result.columns
            if all(
                self._is_number(row.get(column))
                for row in result.rows
                if row.get(column) is not None
            )
        ]
        text_columns = [
            column
            for column in result.columns
            if column not in numeric_columns
            and any(row.get(column) is not None for row in result.rows)
        ]

        if numeric_columns:
            metric = numeric_columns[-1]
            best_row = max(result.rows, key=lambda row: self._as_number(row.get(metric)))
            label = self._row_label(best_row, text_columns)
            value = best_row.get(metric)
            claim = (
                f"{label} 的 {metric} 最高，为 {value}" if label else f"{metric} 最高值为 {value}"
            )
            evidence = f"SQL result row: {self._format_row(best_row)}"
            findings.append(KeyFinding(claim=claim, evidence=evidence))

        findings.append(
            KeyFinding(
                claim=f"本次查询返回 {result.row_count} 行。",
                evidence=f"SQL result row_count = {result.row_count}",
            )
        )
        return findings

    def _build_summary(self, result: QueryResultPayload) -> str:
        columns = "、".join(result.columns) if result.columns else "无列信息"
        return f"SQL 执行成功，返回 {result.row_count} 行，结果列包括：{columns}。"

    def _suggest_followups(self, question: str, result: QueryResultPayload) -> List[str]:
        suggestions = ["是否需要增加时间范围过滤？", "是否需要按类别或部门进一步拆分？"]
        if result.columns:
            suggestions.append(f"是否需要查看 `{result.columns[0]}` 的明细分布？")
        return suggestions

    def _row_label(self, row: Dict[str, Any], text_columns: List[str]) -> str:
        for column in text_columns:
            value = row.get(column)
            if value not in (None, ""):
                return str(value)
        return ""

    def _format_row(self, row: Dict[str, Any]) -> str:
        return ", ".join(f"{key} = {value}" for key, value in row.items())

    def _is_number(self, value: Any) -> bool:
        if value is None:
            return True
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _as_number(self, value: Any) -> float:
        return float(value) if self._is_number(value) and value is not None else float("-inf")


class LLMResultAnalyzer:
    """
    严格 grounded 的 LLM 结果分析器。

    LLM 只能基于 SQL 执行结果生成表达，不允许新增事实。
    一旦输出无法解析、缺少 evidence 或 evidence 不可追溯，就回退到启发式分析。
    """

    def __init__(self, llm, fallback: HeuristicResultAnalyzer | None = None):
        self.llm = llm
        self.fallback = fallback or HeuristicResultAnalyzer()

    def analyze(self, question: str, candidate: SQLCandidate) -> AnalysisResult:
        fallback_result = self.fallback.analyze(question, candidate)
        if not candidate.execution.success or not candidate.execution.preview:
            return fallback_result

        prompt = self._build_prompt(question, candidate, fallback_result.result)
        try:
            response = self.llm.generate(
                [{"role": "system", "content": prompt}],
                temperature=0,
            )
            payload = self._parse_json(response)
            return self._build_analysis(payload, fallback_result)
        except Exception:
            return fallback_result

    def _build_prompt(
        self,
        question: str,
        candidate: SQLCandidate,
        result: QueryResultPayload,
    ) -> str:
        return f"""
你是一个严格基于数据证据回答的分析器。

硬性规则：
1. 只能根据给定 SQL 执行结果回答，不能使用常识或猜测补充数值。
2. 每个 key_findings 条目都必须包含 evidence。
3. evidence 必须能从 SQL result 中直接追溯，例如 "SQL result: cnt = 4"。
4. 如果结果不足以回答问题，必须在 limitations 中说明。
5. 只返回 JSON，不要返回 markdown。

用户问题：
{question}

已执行 SQL：
{candidate.sql}

SQL result：
{json.dumps(result.__dict__, ensure_ascii=False, default=str)}

返回 JSON 格式：
{{
  "answer": "一句直接答案",
  "summary": "简短结果摘要",
  "key_findings": [
    {{"claim": "结论", "evidence": "SQL result: 列 = 值"}}
  ],
  "limitations": ["限制"],
  "followup_questions": ["后续问题"]
}}
""".strip()

    def _parse_json(self, response: str) -> Dict[str, Any]:
        text = response.strip()
        if text.startswith("```"):
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        return json.loads(text)

    def _build_analysis(
        self,
        payload: Dict[str, Any],
        fallback_result: AnalysisResult,
    ) -> AnalysisResult:
        answer = str(payload.get("answer") or fallback_result.answer)
        summary = str(payload.get("summary") or fallback_result.summary)
        if not self._contains_only_grounded_numbers(answer, fallback_result.result):
            raise ValueError("LLM answer contains ungrounded numbers")
        if not self._contains_only_grounded_numbers(summary, fallback_result.result):
            raise ValueError("LLM summary contains ungrounded numbers")

        findings = []
        for item in payload.get("key_findings", []):
            claim = str(item.get("claim", "")).strip()
            evidence = str(item.get("evidence", "")).strip()
            if not claim or not self._is_grounded_evidence(evidence, fallback_result.result):
                raise ValueError("LLM finding lacks grounded evidence")
            if not self._contains_only_grounded_numbers(claim, fallback_result.result):
                raise ValueError("LLM finding claim contains ungrounded numbers")
            findings.append(KeyFinding(claim=claim, evidence=evidence))

        return AnalysisResult(
            answer=answer,
            result=fallback_result.result,
            summary=summary,
            key_findings=findings or fallback_result.key_findings,
            limitations=[str(item) for item in payload.get("limitations", [])]
            or fallback_result.limitations,
            followup_questions=[str(item) for item in payload.get("followup_questions", [])]
            or fallback_result.followup_questions,
        )

    def _is_grounded_evidence(self, evidence: str, result: QueryResultPayload) -> bool:
        if not evidence.startswith("SQL result:"):
            return False
        evidence_text = evidence.removeprefix("SQL result:").strip()
        for row in result.rows:
            for key, value in row.items():
                if str(key) in evidence_text and str(value) in evidence_text:
                    return True
        return False

    def _contains_only_grounded_numbers(self, text: str, result: QueryResultPayload) -> bool:
        numbers = self._extract_numbers(text)
        if not numbers:
            return True

        grounded_numbers = {float(result.row_count)}
        for row in result.rows:
            for value in row.values():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    grounded_numbers.add(float(value))
                elif isinstance(value, str):
                    grounded_numbers.update(float(item) for item in self._extract_numbers(value))

        return all(float(number) in grounded_numbers for number in numbers)

    def _extract_numbers(self, text: str) -> List[str]:
        return re.findall(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9_])", text)
