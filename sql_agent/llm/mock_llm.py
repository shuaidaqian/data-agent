"""本地原型使用的确定性 Mock LLM。"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

from sql_agent.core.config import System
from sql_agent.core.types import LLMConfig
from sql_agent.llm.base import LLMBackend


class MockLLM(LLMBackend):
    """不依赖外部服务的本地 LLM 替身。"""

    def __init__(self, system: System):
        super().__init__(system)
        self.calls = 0

    def generate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        **kwargs: Any,
    ) -> str:
        self.calls += 1
        if messages and "严格基于数据证据回答" in messages[0].get("content", ""):
            return """
            {
              "answer": "当前员工总数为 1 人。",
              "summary": "查询返回 cnt = 1。",
              "key_findings": [
                {"claim": "员工总数为 1 人。", "evidence": "SQL result: cnt = 1"}
              ],
              "limitations": ["该结论仅基于当前数据库快照。"],
              "followup_questions": ["是否需要按部门统计员工数量？"]
            }
            """
        return "可以直接查询。\n```sql\nSELECT COUNT(*) AS cnt FROM employees\n```"

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        yield self.generate(messages, config, **kwargs)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def count_tokens(self, text: str) -> int:
        return len(text.split())
