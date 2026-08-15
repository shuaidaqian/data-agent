"""一次问答请求的 Agent 状态机。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStage(str, Enum):
    """Agent Runtime 的粗粒度阶段。"""

    INIT = "INIT"
    LOAD_CONTEXT = "LOAD_CONTEXT"
    PLAN_QUERY = "PLAN_QUERY"
    GENERATE_SQL = "GENERATE_SQL"
    RANK_CANDIDATES = "RANK_CANDIDATES"
    RECOVER = "RECOVER"
    ANALYZE_RESULT = "ANALYZE_RESULT"
    FINALIZE = "FINALIZE"
    FAILED = "FAILED"


class AgentStatus(str, Enum):
    """Agent Runtime 的执行状态。"""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class AgentState:
    """保存一次自然语言问答在受控 Runtime 中的关键产物。"""

    question: str
    db_connection_id: str
    conversation_id: Optional[str] = None
    stage: AgentStage = AgentStage.INIT
    status: AgentStatus = AgentStatus.RUNNING
    recovery_attempts: int = 0
    error: Optional[str] = None
    prompt: Any = None
    database_connection: Any = None
    conversation: Any = None
    table_descriptions: List[Any] = field(default_factory=list)
    semantic_plan: Any = None
    semantic_candidate_sqls: List[str] = field(default_factory=list)
    agent_result: Any = None
    ranked_candidates: List[Any] = field(default_factory=list)
    selected_candidate: Any = None
    analysis: Any = None
    intermediate_steps: List[Dict[str, str]] = field(default_factory=list)

    def transition_to(
        self,
        stage: AgentStage,
        status: Optional[AgentStatus] = None,
    ) -> "AgentState":
        """推进状态机到指定阶段。"""
        self.stage = stage
        if status is not None:
            self.status = status
        return self

    def fail(self, error: str) -> "AgentState":
        """将状态机标记为失败。"""
        self.error = error
        self.stage = AgentStage.FAILED
        self.status = AgentStatus.FAILED
        return self

    def to_dict(self) -> Dict[str, Any]:
        """输出适合 API 和调试面板消费的轻量摘要。"""
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "question": self.question,
            "db_connection_id": self.db_connection_id,
            "conversation_id": self.conversation_id,
            "recovery_attempts": self.recovery_attempts,
            "error": self.error,
        }
