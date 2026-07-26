"""
OpenAI / Azure OpenAI LLM 实现
"""
from __future__ import annotations

import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import openai
import tiktoken
from overrides import override

from sql_agent.core.config import System
from sql_agent.core.types import LLMConfig
from sql_agent.llm.base import LLMBackend

logger = logging.getLogger(__name__)


class OpenAILLM(LLMBackend):
     """OpenAI / Azure OpenAI LLM 实现"""

     def __init__(self, system: System):
         super().__init__(system)
         settings = system.settings
         self._use_azure = bool(settings.azure_api_key)

         if self._use_azure:
             self._client = openai.AzureOpenAI(
                 api_key=settings.azure_api_key,
                 api_version=settings.azure_api_version or "2024-02-01",
                 azure_endpoint=settings.azure_endpoint,
             )
             self._embedding_model = settings.embedding_model
         else:
             self._client = openai.OpenAI(
                 api_key=settings.openai_api_key,
             )
             self._embedding_model = settings.embedding_model

     @override
     def generate(
         self,
         messages: List[Dict[str, str]],
         config: Optional[LLMConfig] = None,
         **kwargs: Any,
     ) -> str:
         cfg = config or LLMConfig()
         response = self._client.chat.completions.create(
             model=cfg.llm_name,
             messages=messages,
             temperature=kwargs.get("temperature", cfg.temperature),
             max_tokens=kwargs.get("max_tokens", cfg.max_tokens),
         )
         content = response.choices[0].message.content
         logger.debug(
             f"LLM call: model={cfg.llm_name}, "
             f"input_tokens={response.usage.prompt_tokens if response.usage else 'N/A'}, "
             f"output_tokens={response.usage.completion_tokens if response.usage else 'N/A'}"
         )
         return content or ""

     @override
     async def generate_stream(
         self,
         messages: List[Dict[str, str]],
         config: Optional[LLMConfig] = None,
         **kwargs: Any,
     ) -> AsyncIterator[str]:
         cfg = config or LLMConfig()
         stream = self._client.chat.completions.create(
             model=cfg.llm_name,
             messages=messages,
             temperature=kwargs.get("temperature", cfg.temperature),
             max_tokens=kwargs.get("max_tokens", cfg.max_tokens),
             stream=True,
         )
         for chunk in stream:
             delta = chunk.choices[0].delta if chunk.choices else None
             if delta and delta.content:
                 yield delta.content

     @override
     def embed(self, texts: List[str]) -> List[List[float]]:
         response = self._client.embeddings.create(
             model=self._embedding_model,
             input=texts,
         )
         return [r.embedding for r in response.data]

     @override
     def count_tokens(self, text: str) -> int:
         try:
             enc = tiktoken.encoding_for_model("gpt-4")
         except Exception:
             enc = tiktoken.get_encoding("cl100k_base")
         return len(enc.encode(text))
