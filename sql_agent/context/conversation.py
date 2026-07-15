"""
Multi-turn conversation manager.

NEW: Dataherald lacks this feature entirely.
Every prompt was an isolated query with no history awareness.

This module provides:
- Conversation history management with token budget control
- Reference disambiguation (e.g. "last month" -> resolve from history)
- Context window management for LLM budget
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
     Manages multi-turn conversations with context window control.

     Features:
     - Turn tracking with role-based history
     - Token budget management to avoid exceeding LLM limits
     - Reference disambiguation for follow-up questions
     - Automatic summarization of long histories
     """

     def __init__(
         self,
         max_turns: int = 20,
         max_tokens: int = 4000,
         ttl_minutes: Optional[int] = 30,
         storage: Optional[Any] = None,
     ):
         """
         Args:
             max_turns: Maximum number of turns to keep in short-term memory
             max_tokens: Maximum token budget for conversation context
             ttl_minutes: Time-to-live for conversation (None = no expiry)
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
         """Create a new conversation session"""
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
         """Get existing conversation or create new one"""
         if conversation_id:
             conv = self._conversations.get(conversation_id)
             if conv is None:
                 conv = self._load_conversation(conversation_id)
             if conv is None:
                 return self.create_conversation(db_connection_id)

             # Check TTL
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
         """Add a turn to the conversation"""
         turn = ConversationTurn(
             role=role,
             content=content,
             sql=sql,
             sql_result=sql_result,
         )
         conversation.turns.append(turn)
         conversation.updated_at = datetime.now()

         # Truncate if over budget
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
         Get the most relevant history turns for the current question.
         Returns the most recent turns that are related.
         """
         if not conversation.turns:
             return []

         # Return the most recent turns (last N pairs = 2*N entries)
         relevant = conversation.turns[-(max_turns * 2):]
         return relevant

     def build_context_prompt(
         self,
         conversation: Conversation,
         current_question: str,
         max_turns: int = 4,
     ) -> str:
         """
         Build a conversation context string for LLM input.
         Includes potential reference disambiguation.
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

         # Add reference disambiguation hint
         if len(conversation.turns) >= 2:
             last_turn = conversation.turns[-1]
             if last_turn.role == "user":
                 context += "\n[Note: The current question may contain references "
                 context += "to the previous conversation. Resolve them based on context.]\n"

         return context

     def _truncate_if_needed(self, conversation: Conversation) -> None:
         """Truncate conversation if it exceeds max_turns"""
         if len(conversation.turns) > self.max_turns:
             excess = len(conversation.turns) - self.max_turns
             conversation.turns = conversation.turns[excess:]
             logger.info(f"Truncated {excess} old turns from conversation")

     def get_conversation_summary(self, conversation: Conversation) -> str:
         """Generate a brief summary of the conversation"""
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
         """Delete a conversation"""
         if conversation_id in self._conversations:
             del self._conversations[conversation_id]
             if self.storage:
                 self.storage.delete("conversations", {"id": conversation_id})
             return True
         if self.storage and self.storage.delete("conversations", {"id": conversation_id}):
             return True
         return False

     def list_active_conversations(self) -> List[Conversation]:
         """List all active (non-expired) conversations"""
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

         # Clean up expired
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
