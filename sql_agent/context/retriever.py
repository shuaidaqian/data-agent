"""
用于 few-shot 示例和管理员指令的上下文检索器。

负责：
- 对 Golden SQL 做向量相似度检索（与 Dataherald 类似）
- 根据 db_connection_id 检索管理员指令
- 支持 schema 感知过滤扩展
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sql_agent.core.types import Prompt
from sql_agent.storage.vector import VectorBackend

logger = logging.getLogger(__name__)

COLLECTION_GOLDEN_SQL = "golden_sqls"


class ContextRetriever:
    """
    为 NL-to-SQL 检索上下文（few-shot 示例 + 管理员指令）。
    """

    def __init__(
        self,
        vector_store: VectorBackend,
        db_storage: Any,  # StorageBackend
    ):
        self.vector_store = vector_store
        self.db_storage = db_storage

    def retrieve_few_shot_examples(
        self,
        prompt: Prompt,
        number_of_samples: int = 5,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        使用向量相似度检索相关 Golden SQL 示例。
        """
        results = self.vector_store.query(
            query_texts=[prompt.text],
            db_connection_id=prompt.db_connection_id,
            collection=COLLECTION_GOLDEN_SQL,
            num_results=number_of_samples,
        )

        if not results:
            return None

        samples = []
        for res in results:
            # 从存储中加载完整 Golden SQL
            golden = self.db_storage.find_one("golden_sqls", {"_id": res.get("id")})
            if golden:
                samples.append(
                    {
                        "prompt_text": golden.get("prompt_text", ""),
                        "sql": golden.get("sql", ""),
                        "score": res.get("score", 0),
                        "tables_used": golden.get("tables_used", []),
                    }
                )

        return samples if samples else None

    def retrieve_instructions(
        self,
        db_connection_id: str,
    ) -> Optional[List[Dict[str, str]]]:
        """
        检索指定数据库连接的管理员指令。
        """
        instructions = self.db_storage.find(
            "instructions",
            {"db_connection_id": db_connection_id},
        )

        if not instructions:
            return None

        return [{"instruction": inst.get("instruction", "")} for inst in instructions]

    def retrieve_all_context(
        self,
        prompt: Prompt,
        number_of_samples: int = 5,
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, str]]]]:
        """
        便捷方法：同时检索 few-shot 示例和管理员指令。
        """
        examples = self.retrieve_few_shot_examples(prompt, number_of_samples)
        instructions = self.retrieve_instructions(prompt.db_connection_id)
        return examples, instructions
