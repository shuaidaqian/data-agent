"""
LLM 后端抽象层。

定义 LLM 服务提供方接口。
当前支持 OpenAI、Azure OpenAI，并可扩展到其他模型服务。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from sql_agent.core.config import Component, System
from sql_agent.core.types import LLMConfig


class LLMBackend(Component, ABC):
     """LLM 后端抽象接口"""

     def __init__(self, system: System):
         super().__init__(system)
         self._system = system

     @abstractmethod
     def generate(
         self,
         messages: List[Dict[str, str]],
         config: Optional[LLMConfig] = None,
         **kwargs: Any,
     ) -> str:
         """调用 LLM 生成回复"""
         ...

     @abstractmethod
     def generate_stream(
         self,
         messages: List[Dict[str, str]],
         config: Optional[LLMConfig] = None,
         **kwargs: Any,
     ) -> AsyncIterator[str]:
         """流式调用 LLM 生成回复"""
         ...

     @abstractmethod
     def embed(self, texts: List[str]) -> List[List[float]]:
         """为给定文本生成 embedding"""
         ...

     @abstractmethod
     def count_tokens(self, text: str) -> int:
         """统计文本中的 token 数量"""
         ...
