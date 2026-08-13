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
    expected_visualization_type: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """评估指标汇总。"""

    total: int
    valid_rate: float
    execution_accuracy: float
    answer_grounding_rate: float
    semantic_plan_accuracy: float
    verified_query_hit_rate: float = 0.0
    tag_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    error_breakdown: Dict[str, int] = field(default_factory=dict)

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
                "",
                "## Tag Metrics",
                *[
                    f"- {tag}: total={metrics['total']}, valid_rate={metrics['valid_rate']:.2f}, execution_accuracy={metrics['execution_accuracy']:.2f}, grounding_rate={metrics['grounding_rate']:.2f}"
                    for tag, metrics in sorted(self.tag_metrics.items())
                ],
                "",
                "## Error Breakdown",
                *[
                    f"- {error_type}: {count}"
                    for error_type, count in sorted(self.error_breakdown.items())
                ],
            ]
        )


class EvaluationHarness:
    """基于标准响应 dict 计算 Data Agent 质量指标。"""

    def __init__(self, cases: List[EvaluationCase]):
        self.cases = cases

    @classmethod
    def from_cases(cls, cases: List[Dict[str, Any]]) -> "EvaluationHarness":
        return cls([EvaluationCase(**item) for item in cases])

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
        grounded_total = 0
        semantic = 0
        verified_hits = 0
        tag_buckets: Dict[str, Dict[str, int]] = {}
        error_breakdown = {
            "SEMANTIC_MISS": 0,
            "SQL_INVALID": 0,
            "EXECUTION_MISMATCH": 0,
            "UNGROUNDED_ANSWER": 0,
            "MISSING_EVIDENCE": 0,
            "WRONG_VISUALIZATION": 0,
        }
        for case in self.cases:
            response = responses.get(case.id, {})
            valid_sql = self._is_valid_sql_response(case, response)
            execution_match = self._matches_expected_result(case, response)
            grounded_match = self._is_grounded(case, response)
            semantic_match = self._matches_semantic_plan(case, response)
            visualization_match = self._matches_visualization(case, response)

            if valid_sql:
                valid += 1
            else:
                error_breakdown["SQL_INVALID"] += 1
            if execution_match:
                execution += 1
            else:
                error_breakdown["EXECUTION_MISMATCH"] += 1
            if grounded_match:
                grounded_total += 1
                grounded_count = 1
            else:
                grounded_count = 0
                error_breakdown["UNGROUNDED_ANSWER"] += 1
                if case.required_evidence:
                    error_breakdown["MISSING_EVIDENCE"] += 1
            if semantic_match:
                semantic += 1
            else:
                error_breakdown["SEMANTIC_MISS"] += 1
            if not visualization_match:
                error_breakdown["WRONG_VISUALIZATION"] += 1
            if response.get("used_verified_query"):
                verified_hits += 1
            for tag in case.tags:
                bucket = tag_buckets.setdefault(
                    tag,
                    {"total": 0, "valid": 0, "execution": 0, "grounded": 0},
                )
                bucket["total"] += 1
                bucket["valid"] += int(valid_sql)
                bucket["execution"] += int(execution_match)
                bucket["grounded"] += grounded_count

        return EvaluationReport(
            total=total,
            valid_rate=valid / total,
            execution_accuracy=execution / total,
            answer_grounding_rate=grounded_total / total,
            semantic_plan_accuracy=semantic / total,
            verified_query_hit_rate=verified_hits / total,
            tag_metrics=self._build_tag_metrics(tag_buckets),
            error_breakdown=error_breakdown,
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

    def _matches_visualization(self, case: EvaluationCase, response: Dict[str, Any]) -> bool:
        visualization = response.get("visualization", {})
        if visualization.get("validation", {}).get("valid") is False:
            return False
        if not case.expected_visualization_type:
            return True
        return visualization.get("chart_type") == case.expected_visualization_type

    def _build_tag_metrics(
        self, tag_buckets: Dict[str, Dict[str, int]]
    ) -> Dict[str, Dict[str, Any]]:
        output = {}
        for tag, bucket in tag_buckets.items():
            total = bucket["total"] or 1
            output[tag] = {
                "total": bucket["total"],
                "valid_rate": bucket["valid"] / total,
                "execution_accuracy": bucket["execution"] / total,
                "grounding_rate": bucket["grounded"] / total,
            }
        return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="运行 Data Agent 离线评估。")
    parser.add_argument("cases", help="评估用例 YAML 路径")
    args = parser.parse_args()
    report = EvaluationHarness.from_yaml(args.cases).evaluate_responses({})
    print(report.to_markdown())
