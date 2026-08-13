"""API 端到端评估运行器。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib import request

import yaml

from sql_agent.eval.harness import EvaluationHarness


@dataclass
class DemoSQLiteBuilder:
    """构造可重复的 SQLite demo 数据库。"""

    base_dir: Path

    def build(self, name: str = "data_agent_eval_demo.db") -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.base_dir / name
        if db_path.exists():
            db_path.unlink()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department TEXT, status TEXT)"
            )
            conn.execute(
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, status TEXT, created_at TEXT)"
            )
            conn.executemany(
                "INSERT INTO employees VALUES (?, ?, ?, ?)",
                [
                    (1, "Alice", "研发", "active"),
                    (2, "Bob", "销售", "active"),
                    (3, "Cathy", "研发", "inactive"),
                ],
            )
            conn.executemany(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                [
                    (1, 1, 100.0, "paid", "2026-08-01"),
                    (2, 1, 50.0, "paid", "2026-08-02"),
                    (3, 2, 30.0, "cancelled", "2026-08-03"),
                ],
            )
            conn.commit()
        return db_path


@dataclass
class ApiCaseRunner:
    """批量调用 `/api/v1/question` 的评估客户端。"""

    api_base_url: str
    db_connection_id: str
    timeout_seconds: int = 30

    def build_payload(self, case: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "question": case["question"],
            "db_connection_id": case.get("db_connection_id", self.db_connection_id),
            "conversation_id": case.get("conversation_id"),
        }

    def run_cases(self, cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        responses = {}
        for case in cases:
            responses[case["id"]] = self._post_question(self.build_payload(case))
        return responses

    def _post_question(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.api_base_url.rstrip('/')}/api/v1/question",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def write_markdown_report(
    output_dir: Path,
    markdown: str,
    timestamp: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = output_dir / f"{timestamp}.md"
    report_path.write_text(markdown, encoding="utf-8")
    return report_path


def _load_cases(path: Path) -> List[Dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("cases", []))


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Data Agent API 端到端 benchmark。")
    parser.add_argument("--cases", required=True, help="评估用例 YAML 路径")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--db-connection-id", default="demo")
    parser.add_argument("--output-dir", default="docs/eval-reports")
    parser.add_argument("--build-demo-db", action="store_true")
    args = parser.parse_args()

    if args.build_demo_db:
        db_path = DemoSQLiteBuilder(Path("data")).build()
        print(f"demo SQLite 已生成：{db_path}")

    cases = _load_cases(Path(args.cases))
    responses = ApiCaseRunner(args.api_base_url, args.db_connection_id).run_cases(cases)
    report = EvaluationHarness.from_cases(cases).evaluate_responses(responses)
    report_path = write_markdown_report(Path(args.output_dir), report.to_markdown())
    print(f"评估报告已生成：{report_path}")


if __name__ == "__main__":
    main()
