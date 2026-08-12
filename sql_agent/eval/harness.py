"""Data Agent 离线评估工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class EvaluationCase:
    """单条评估样例。"""

    id: str
    question: str
    expected_sql_contains: List[str] = field(default_factory=list)
    expected_result: Dict[str, Any] = field(default_factory=dict)
    expected_semantic_metrics: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """评估指标汇总。"""

    total: int
    valid_rate: float
    execution_accuracy: float
    answer_grounding_rate: float
    semantic_plan_accuracy: float
    verified_query_hit_rate: float = 0.0

    def to_markdown(self) -> str:
        return "\n".join(
            [
                "# Data Agent Evaluation Report",
                "",
                f"total: {self.total}",
                f"valid_rate: {self.valid_rate:.2f}",
                f"execution_accuracy: {self.execution_accuracy:.2f}",
                f"answer_grounding_rate: {self.answer_grounding_rate:.2f}",
                f"semantic_plan_accuracy: {self.semantic_plan_accuracy:.2f}",
                f"verified_query_hit_rate: {self.verified_query_hit_rate:.2f}",
            ]
        )


class EvaluationHarness:
    """基于标准响应 dict 计算 Data Agent 质量指标。"""

    def __init__(self, cases: List[EvaluationCase]):
        self.cases = cases

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EvaluationHarness":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        cases = [EvaluationCase(**item) for item in data.get("cases", [])]
        return cls(cases)

    def evaluate_responses(self, responses: Dict[str, Dict[str, Any]]) -> EvaluationReport:
        total = len(self.cases)
        if total == 0:
            return EvaluationReport(0, 0.0, 0.0, 0.0, 0.0)

        valid = 0
        execution = 0
        grounded = 0
        semantic = 0
        verified_hits = 0
        for case in self.cases:
            response = responses.get(case.id, {})
            if self._is_valid_sql_response(case, response):
                valid += 1
            if self._matches_expected_result(case, response):
                execution += 1
            if self._is_grounded(case, response):
                grounded += 1
            if self._matches_semantic_plan(case, response):
                semantic += 1
            if response.get("used_verified_query"):
                verified_hits += 1

        return EvaluationReport(
            total=total,
            valid_rate=valid / total,
            execution_accuracy=execution / total,
            answer_grounding_rate=grounded / total,
            semantic_plan_accuracy=semantic / total,
            verified_query_hit_rate=verified_hits / total,
        )

    def _is_valid_sql_response(self, case: EvaluationCase, response: Dict[str, Any]) -> bool:
        sql = str(response.get("sql", ""))
        if response.get("status") != "VALID":
            return False
        return all(token.lower() in sql.lower() for token in case.expected_sql_contains)

    def _matches_expected_result(self, case: EvaluationCase, response: Dict[str, Any]) -> bool:
        rows = response.get("result", {}).get("rows", [])
        if not rows:
            return not case.expected_result
        first_row = rows[0]
        return all(first_row.get(key) == value for key, value in case.expected_result.items())

    def _is_grounded(self, case: EvaluationCase, response: Dict[str, Any]) -> bool:
        findings = response.get("analysis", {}).get("key_findings", [])
        evidences = [str(item.get("evidence", "")) for item in findings]
        return all(required in evidences for required in case.required_evidence)

    def _matches_semantic_plan(self, case: EvaluationCase, response: Dict[str, Any]) -> bool:
        metrics = response.get("semantic_plan", {}).get("metrics", [])
        return all(metric in metrics for metric in case.expected_semantic_metrics)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="运行 Data Agent 离线评估。")
    parser.add_argument("cases", help="评估用例 YAML 路径")
    args = parser.parse_args()
    report = EvaluationHarness.from_yaml(args.cases).evaluate_responses({})
    print(report.to_markdown())
