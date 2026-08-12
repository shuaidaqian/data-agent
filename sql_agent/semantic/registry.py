"""语义模型注册表。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml

from sql_agent.semantic.types import (
    DimensionDefinition,
    MetricDefinition,
    SemanticFilter,
    SemanticModel,
)


class SemanticModelRegistry:
    """负责加载和检索轻量语义模型。"""

    def __init__(self, model: SemanticModel):
        self.model = model

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SemanticModelRegistry":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        metrics = [
            MetricDefinition(
                name=item["name"],
                label=item.get("label", item["name"]),
                table=item["table"],
                expression=item["expression"],
                synonyms=list(item.get("synonyms", [])),
                default_filters=[
                    SemanticFilter(
                        field=filter_item["field"],
                        op=filter_item.get("op", "="),
                        value=filter_item.get("value"),
                    )
                    for filter_item in item.get("default_filters", [])
                ],
                description=item.get("description"),
            )
            for item in data.get("metrics", [])
        ]
        dimensions = [
            DimensionDefinition(
                name=item["name"],
                label=item.get("label", item["name"]),
                table=item["table"],
                column=item["column"],
                synonyms=list(item.get("synonyms", [])),
                description=item.get("description"),
            )
            for item in data.get("dimensions", [])
        ]
        return cls(
            SemanticModel(
                version=int(data.get("version", 1)),
                db_connection_id=data.get("db_connection_id", ""),
                metrics=metrics,
                dimensions=dimensions,
            )
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticModelRegistry":
        tmp = Path("__semantic_model_tmp.yml")
        try:
            tmp.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            return cls.from_yaml(tmp)
        finally:
            if tmp.exists():
                tmp.unlink()

    def find_metric(self, question: str) -> Optional[MetricDefinition]:
        return self._find_by_terms(question, self.model.metrics)

    def find_dimension(self, question: str) -> Optional[DimensionDefinition]:
        return self._find_by_terms(question, self.model.dimensions)

    def metric_by_name(self, name: str) -> Optional[MetricDefinition]:
        return next((metric for metric in self.model.metrics if metric.name == name), None)

    def dimension_by_name(self, name: str) -> Optional[DimensionDefinition]:
        return next((dim for dim in self.model.dimensions if dim.name == name), None)

    def _find_by_terms(self, question: str, items: Iterable[Any]):
        normalized = question.lower()
        for item in items:
            if any(term and term.lower() in normalized for term in item.terms()):
                return item
        return None
