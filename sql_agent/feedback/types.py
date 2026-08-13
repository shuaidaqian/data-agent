"""反馈闭环数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class WrongReason(str, Enum):
    """结构化错误原因。"""

    WRONG_TABLE = "WRONG_TABLE"
    WRONG_COLUMN = "WRONG_COLUMN"
    WRONG_FILTER = "WRONG_FILTER"
    WRONG_JOIN = "WRONG_JOIN"
    WRONG_AGGREGATION = "WRONG_AGGREGATION"
    WRONG_METRIC_DEFINITION = "WRONG_METRIC_DEFINITION"
    UNGROUNDED_ANSWER = "UNGROUNDED_ANSWER"
    VISUALIZATION_WRONG = "VISUALIZATION_WRONG"


class VerifiedQueryLifecycle(str, Enum):
    """verified query 生命周期。"""

    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    DEPRECATED = "DEPRECATED"
    REJECTED = "REJECTED"


@dataclass
class QueryFeedback:
    """用户对一次数据问答结果的反馈。"""

    question: str
    db_connection_id: str
    sql: str
    answer_correct: bool
    sql_correct: bool
    id: Optional[str] = None
    wrong_reason: Optional[str] = None
    corrected_sql: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerifiedQuery:
    """经过用户修正或确认的可信查询。"""

    question: str
    sql: str
    db_connection_id: str
    id: Optional[str] = None
    source_feedback_id: Optional[str] = None
    lifecycle: str = VerifiedQueryLifecycle.PENDING_REVIEW.value
    quality_signals: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerifiedQueryMatch:
    """可信查询召回结果。"""

    question: str
    sql: str
    score: float
    id: Optional[str] = None
