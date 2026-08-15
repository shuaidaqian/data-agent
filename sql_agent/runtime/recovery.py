"""候选 SQL 失败恢复环路。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional

from sql_agent.ranking.candidate import SQLCandidate


@dataclass
class RecoveryDecision:
    """恢复环路输出。"""

    attempted: bool = False
    recovered: bool = False
    reason: str = "最佳候选已可用，无需恢复"
    selected_candidate: Optional[SQLCandidate] = None
    recovery_attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["selected_candidate"] = (
            self.selected_candidate.to_dict() if self.selected_candidate else None
        )
        return payload


class RecoveryLoop:
    """基于执行证据选择可恢复候选，避免直接把失败结果返回给用户。"""

    def recover(self, candidates: Iterable[SQLCandidate]) -> RecoveryDecision:
        ranked = list(candidates)
        if not ranked:
            return RecoveryDecision(
                attempted=True,
                recovered=False,
                reason="没有可恢复候选：候选列表为空",
                recovery_attempts=1,
            )

        best = ranked[0]
        if self._is_usable(best):
            return RecoveryDecision(
                attempted=False,
                recovered=True,
                selected_candidate=best,
            )

        for candidate in ranked[1:]:
            if self._is_usable(candidate):
                return RecoveryDecision(
                    attempted=True,
                    recovered=True,
                    reason="最佳候选不可用，已选择下一个可执行候选",
                    selected_candidate=candidate,
                    recovery_attempts=1,
                )

        return RecoveryDecision(
            attempted=True,
            recovered=False,
            reason="没有可恢复候选：所有候选均未通过安全校验或执行验证",
            recovery_attempts=1,
        )

    def _is_usable(self, candidate: SQLCandidate) -> bool:
        return candidate.status == "VALID" and candidate.execution.success
