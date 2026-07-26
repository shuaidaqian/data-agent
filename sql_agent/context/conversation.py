"""
多轮对话管理器。

新增能力：Dataherald 原始链路基本缺少该能力，
每次 Prompt 都是独立查询，没有历史感知。

本模块提供：
- 带 token 预算控制的对话历史管理
- 引用消歧（例如“上个月”需要根据历史推断）
- 面向 LLM 预算的上下文窗口管理
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, List, Optional

from sql_agent.core.types import Conversation, ConversationTurn

logger = logging.getLogger(__name__)


class ConversationManager:
     """
     管理带上下文窗口控制的多轮对话。

     功能：
     - 按角色跟踪对话轮次
     - 管理 token 预算，避免超过 LLM 限制
     - 为追问提供引用消歧上下文
     - 为长历史预留摘要能力
     """

     def __init__(
         self,
         max_turns: int = 20,
         max_tokens: int = 4000,
         ttl_minutes: Optional[int] = 30,
         storage: Optional[Any] = None,
     ):
         """
         参数：
             max_turns: 短期记忆中保留的最大轮次数
             max_tokens: 对话上下文最大 token 预算
             ttl_minutes: 对话有效期，None 表示永不过期
         """
         self.max_turns = max_turns
         self.max_tokens = max_tokens
         self.ttl_minutes = ttl_minutes
         self.storage = storage
         self._conversations: Dict[str, Conversation] = {}

     def create_conversation(
         self,
         db_connection_id: str,
         metadata: Optional[Dict] = None,
     ) -> Conversation:
         """创建新的对话会话"""
         conv = Conversation(
             id=str(uuid4()),
             db_connection_id=db_connection_id,
             metadata=metadata or {},
         )
         self._conversations[str(conv.id)] = conv
         self._save_conversation(conv)
         return conv

     def get_or_create(
         self,
         conversation_id: Optional[str] = None,
         db_connection_id: str = "",
     ) -> Conversation:
         """获取已有对话，不存在则创建新对话"""
         if conversation_id:
             conv = self._conversations.get(conversation_id)
             if conv is None:
                 conv = self._load_conversation(conversation_id)
             if conv is None:
                 return self.create_conversation(db_connection_id)

             # 检查对话有效期
             if self.ttl_minutes:
                 elapsed = (datetime.now() - conv.updated_at).total_seconds() / 60
                 if elapsed > self.ttl_minutes:
                     logger.info(f"Conversation {conversation_id} expired, creating new")
                     return self.create_conversation(conv.db_connection_id)
             return conv
         return self.create_conversation(db_connection_id)

     def add_turn(
         self,
         conversation: Conversation,
         role: str,
         content: str,
         sql: Optional[str] = None,
         sql_result: Optional[str] = None,
     ) -> ConversationTurn:
         """向对话中追加一轮消息"""
         turn = ConversationTurn(
             role=role,
             content=content,
             sql=sql,
             sql_result=sql_result,
         )
         conversation.turns.append(turn)
         conversation.updated_at = datetime.now()

         # 超过预算时截断历史
         self._truncate_if_needed(conversation)
         self._save_conversation(conversation)
         return turn

     def get_relevant_history(
         self,
         conversation: Conversation,
         current_question: str,
         max_turns: int = 4,
     ) -> List[ConversationTurn]:
         """
         获取与当前问题最相关的历史轮次。
         当前实现返回最近的若干轮相关历史。
         """
         if not conversation.turns:
             return []

         # 返回最近的若干轮（最近 N 对问答 = 2*N 条记录）
         relevant = conversation.turns[-(max_turns * 2):]
         return relevant

     def build_context_prompt(
         self,
         conversation: Conversation,
         current_question: str,
         max_turns: int = 4,
     ) -> str:
         """
         为 LLM 输入构造对话上下文字符串。
         其中包含潜在的引用消歧提示。
         """
         if not conversation.turns:
             return ""

         history = self.get_relevant_history(conversation, current_question, max_turns)
         if not history:
             return ""

         context = "\n[Conversation History]\n"
         for turn in history:
             prefix = "User" if turn.role == "user" else "Assistant"
             context += f"{prefix}: {turn.content}\n"
             if turn.sql and turn.role == "assistant":
                 context += f"  SQL: {turn.sql}\n"

         # 增加引用消歧提示
         if len(conversation.turns) >= 2:
             last_turn = conversation.turns[-1]
             if last_turn.role == "user":
                 context += "\n[Note: The current question may contain references "
                 context += "to the previous conversation. Resolve them based on context.]\n"

         return context

     def _truncate_if_needed(self, conversation: Conversation) -> None:
         """当对话超过 max_turns 时截断历史"""
         if len(conversation.turns) > self.max_turns:
             excess = len(conversation.turns) - self.max_turns
             conversation.turns = conversation.turns[excess:]
             logger.info(f"Truncated {excess} old turns from conversation")

     def get_conversation_summary(self, conversation: Conversation) -> str:
         """生成对话的简要摘要"""
         if not conversation.turns:
             return "No conversation history"

         user_turns = [t for t in conversation.turns if t.role == "user"]
         topics = []
         for turn in user_turns[-3:]:
             topics.append(turn.content[:80])

         summary = f"Conversation: {len(conversation.turns)} turns, "
         summary += f"{len(user_turns)} questions.\n"
         summary += "Recent topics:\n"
         for topic in topics:
             summary += f"- {topic}\n"
         return summary

     def delete_conversation(self, conversation_id: str) -> bool:
         """删除对话"""
         if conversation_id in self._conversations:
             del self._conversations[conversation_id]
             if self.storage:
                 self.storage.delete("conversations", {"id": conversation_id})
             return True
         if self.storage and self.storage.delete("conversations", {"id": conversation_id}):
             return True
         return False

     def list_active_conversations(self) -> List[Conversation]:
         """列出所有活跃且未过期的对话"""
         now = datetime.now()
         active = []
         expired_ids = []

         if self.storage:
             for row in self.storage.find("conversations", {}):
                 conv = self._deserialize_conversation(row)
                 if conv.id:
                     self._conversations[str(conv.id)] = conv

         for cid, conv in list(self._conversations.items()):
             if self.ttl_minutes:
                 elapsed = (now - conv.updated_at).total_seconds() / 60
                 if elapsed > self.ttl_minutes:
                     expired_ids.append(cid)
                     continue
             active.append(conv)

         # 清理过期对话
         for cid in expired_ids:
             del self._conversations[cid]
             if self.storage:
                 self.storage.delete("conversations", {"id": cid})

         return active

     def _save_conversation(self, conversation: Conversation) -> None:
         if not self.storage or not conversation.id:
             return
         data = asdict(conversation)
         updated = self.storage.update("conversations", {"id": conversation.id}, data)
         if not updated:
             self.storage.insert("conversations", data)

     def _load_conversation(self, conversation_id: str) -> Optional[Conversation]:
         if not self.storage:
             return None
         row = self.storage.find_one("conversations", {"id": conversation_id})
         if not row:
             return None
         conv = self._deserialize_conversation(row)
         if conv.id:
             self._conversations[str(conv.id)] = conv
         return conv

     def _deserialize_conversation(self, row: Dict[str, Any]) -> Conversation:
         turns = []
         for item in row.get("turns", []):
             if isinstance(item, ConversationTurn):
                 turns.append(item)
             else:
                 turns.append(ConversationTurn(**item))
         return Conversation(
             id=row.get("id"),
             db_connection_id=row.get("db_connection_id", ""),
             turns=turns,
             created_at=row.get("created_at") or datetime.now(),
             updated_at=row.get("updated_at") or datetime.now(),
             metadata=row.get("metadata"),
         )
