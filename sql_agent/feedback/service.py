"""反馈保存和可信查询召回服务。"""

from __future__ import annotations

import re
from typing import List

from sql_agent.feedback.types import QueryFeedback, VerifiedQuery, VerifiedQueryMatch
from sql_agent.storage.db import StorageBackend


class FeedbackService:
    """将用户反馈沉淀为可复用的 verified query。"""

    FEEDBACK_COLLECTION = "query_feedback"
    VERIFIED_COLLECTION = "verified_queries"

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def submit_feedback(self, feedback: QueryFeedback) -> str:
        feedback_id = self.storage.insert(self.FEEDBACK_COLLECTION, feedback.to_dict())
        if feedback.corrected_sql:
            verified = VerifiedQuery(
                question=feedback.question,
                sql=feedback.corrected_sql,
                db_connection_id=feedback.db_connection_id,
                source_feedback_id=feedback_id,
            )
            self.storage.insert(self.VERIFIED_COLLECTION, verified.to_dict())
        return feedback_id

    def list_feedback(self, db_connection_id: str) -> List[QueryFeedback]:
        rows = self.storage.find(self.FEEDBACK_COLLECTION, {"db_connection_id": db_connection_id})
        return [QueryFeedback(**self._filter_feedback(row)) for row in rows]

    def list_verified_queries(self, db_connection_id: str) -> List[VerifiedQuery]:
        rows = self.storage.find(self.VERIFIED_COLLECTION, {"db_connection_id": db_connection_id})
        return [VerifiedQuery(**self._filter_verified(row)) for row in rows]

    def retrieve_verified_queries(
        self,
        question: str,
        db_connection_id: str,
        limit: int = 3,
    ) -> List[VerifiedQueryMatch]:
        verified_queries = self.list_verified_queries(db_connection_id)
        matches = [
            VerifiedQueryMatch(
                id=query.id,
                question=query.question,
                sql=query.sql,
                score=self._similarity(question, query.question),
            )
            for query in verified_queries
        ]
        return [
            match
            for match in sorted(matches, key=lambda item: item.score, reverse=True)
            if match.score > 0
        ][:limit]

    def _similarity(self, left: str, right: str) -> float:
        left_tokens = set(self._tokens(left))
        right_tokens = set(self._tokens(right))
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    def _tokens(self, text: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
        tokens.extend(cjk_chars)
        tokens.extend(
            "".join(cjk_chars[index : index + 2]) for index in range(max(len(cjk_chars) - 1, 0))
        )
        return tokens

    def _filter_feedback(self, row):
        fields = QueryFeedback.__dataclass_fields__
        return {key: value for key, value in row.items() if key in fields}

    def _filter_verified(self, row):
        fields = VerifiedQuery.__dataclass_fields__
        return {key: value for key, value in row.items() if key in fields}
