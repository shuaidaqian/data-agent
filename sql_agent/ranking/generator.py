"""从 Agent 输出中抽取候选 SQL。"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional


class CandidateGenerator:
    """从主 SQL 和中间步骤中收集候选 SQL。"""

    @staticmethod
    def collect(
        primary_sql: Optional[str], step_texts: Optional[Iterable[str]] = None
    ) -> List[str]:
        candidates: List[str] = []
        if primary_sql:
            candidates.append(primary_sql)

        for text in step_texts or []:
            candidates.extend(CandidateGenerator.extract_sql_blocks(text))

        return CandidateGenerator.deduplicate(candidates)

    @staticmethod
    def extract_sql_blocks(text: str) -> List[str]:
        blocks = re.findall(r"```(?:sql|SQL)?\s*(.*?)\s*```", text or "", re.DOTALL)
        return [block.strip().rstrip(";") for block in blocks if block.strip()]

    @staticmethod
    def deduplicate(candidates: Iterable[str]) -> List[str]:
        seen = set()
        output = []
        for sql in candidates:
            normalized = " ".join(sql.strip().rstrip(";").split()).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append(sql.strip().rstrip(";"))
        return output
