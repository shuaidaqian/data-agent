"""
LLM backend abstraction layer

Defines the interface for LLM providers.
Supports OpenAI, Azure OpenAI, and can be extended to other providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from sql_agent.core.config import Component, System
from sql_agent.core.types import LLMConfig


class LLMBackend(Component, ABC):
     """Abstract LLM backend interface"""

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
         """Generate a completion from the LLM"""
         ...

     @abstractmethod
     def generate_stream(
         self,
         messages: List[Dict[str, str]],
         config: Optional[LLMConfig] = None,
         **kwargs: Any,
     ) -> AsyncIterator[str]:
         """Stream a completion from the LLM"""
         ...

     @abstractmethod
     def embed(self, texts: List[str]) -> List[List[float]]:
         """Generate embeddings for the given texts"""
         ...

     @abstractmethod
     def count_tokens(self, text: str) -> int:
         """Count the number of tokens in the text"""
         ...
