"""
核心数据模型定义

定义了整个 NL→SQL Agent 系统的数据模型。
相比 Dataherald 的 types.py，增强了多轮对话支持和复杂查询元数据。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ─── 数据库连接 ───────────────────────────────────────────


@dataclass
class DatabaseConnection:
    """数据库连接配置"""

    id: Optional[str] = None
    alias: str = ""
    connection_uri: str = ""
    schemas: Optional[List[str]] = None
    llm_api_key: Optional[str] = None
    use_ssh: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def decrypt_api_key(self) -> Optional[str]:
        return self.llm_api_key


# ─── Schema 相关 ───────────────────────────────────────────


@dataclass
class ColumnMetadata:
    """列元数据"""

    name: str
    data_type: str
    description: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: Optional[str] = None  # 格式："schema.table.column"
    low_cardinality: bool = False
    categories: Optional[List[str]] = None
    sample_values: Optional[List[str]] = None
    semantic_type: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    distinct_count: Optional[int] = None
    null_count: Optional[int] = None


@dataclass
class TableDescription:
    """表结构描述"""

    id: Optional[str] = None
    table_name: str = ""
    schema_name: Optional[str] = None
    db_connection_id: str = ""
    columns: List[ColumnMetadata] = field(default_factory=list)
    description: Optional[str] = None
    table_schema: str = ""  # DDL 或 CREATE TABLE 语句
    row_count: Optional[int] = None
    status: str = "SCANNED"


# ─── Prompt / 对话 ─────────────────────────────────────────


@dataclass
class Prompt:
    """用户提问（单轮）"""

    id: Optional[str] = None
    text: str = ""
    db_connection_id: str = ""
    schemas: Optional[List[str]] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConversationTurn:
    """
    对话历史中的一轮交互
    相比 Dataherald 的独立提问，这里保存了完整的历史上下文
    """

    role: str  # "user" | "assistant" | "system"
    content: str
    sql: Optional[str] = None
    sql_result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Conversation:
    """
    多轮对话会话
    新增：Dataherald 缺失的多轮对话管理
    """

    id: Optional[str] = None
    db_connection_id: str = ""
    turns: List[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


# ─── SQL 生成 ──────────────────────────────────────────────


class SQLStatus(str, Enum):
    """SQL 状态"""

    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    EXECUTED = "EXECUTED"
    CORRECTED = "CORRECTED"  # 新增：经自纠错后修正


@dataclass
class IntermediateStep:
    """Agent 推理中间步骤"""

    thought: str = ""
    action: str = ""
    action_input: str = ""
    observation: str = ""


@dataclass
class SQLGeneration:
    """SQL 生成结果"""

    id: Optional[str] = None
    prompt_id: str = ""
    conversation_id: Optional[str] = None  # 新增：关联多轮对话
    sql: Optional[str] = None
    status: str = SQLStatus.PENDING
    confidence_score: Optional[float] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    intermediate_steps: Optional[List[IntermediateStep]] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    # 新增：自纠正相关字段
    correction_rounds: int = 0
    sql_before_correction: Optional[str] = None
    correction_reason: Optional[str] = None


@dataclass
class NLGeneration:
    """自然语言回答"""

    id: Optional[str] = None
    sql_generation_id: str = ""
    conversation_id: Optional[str] = None
    text: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


# ─── 示例 & 指令 ──────────────────────────────────────────


@dataclass
class GoldenSQL:
    """黄金示例（Few-shot 训练样本）"""

    id: Optional[str] = None
    prompt_text: str = ""
    sql: str = ""
    db_connection_id: str = ""
    tables_used: Optional[List[str]] = None
    complexity: str = "simple"  # simple / medium / complex
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Instruction:
    """管理员指令"""

    id: Optional[str] = None
    instruction: str = ""
    db_connection_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)


# ─── LLM 配置 ──────────────────────────────────────────────


@dataclass
class LLMConfig:
    """LLM 配置"""

    llm_name: str = os.getenv("LLM_NAME", "gpt-4o")
    api_base: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class AgentConfig:
    """
    Agent 路由配置
    新增：根据查询复杂度自动选择 Agent 模式
    """

    mode: str = "auto"  # 可选值："react" | "plan_solve" | "auto"
    max_iterations: int = 15
    max_execution_time: int = 150
    enable_self_correction: bool = True
    enable_conversation_history: bool = True
    max_fewshot_samples: int = 5
