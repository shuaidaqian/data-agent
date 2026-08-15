"""
FastAPI 路由定义。

对外暴露 NL-to-SQL 功能的 REST API。
设计目标是作为 Dataherald API 层的轻量替代实现。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from sql_agent.core.config import Settings, System
from sql_agent.core.types import (
    DatabaseConnection,
    GoldenSQL,
)
from sql_agent.runtime.question_runtime import DatabaseConnectionNotFound, QuestionRuntime
from sql_agent.sql.database import SQLDatabase
from sql_agent.sql.scanner import SchemaScanner
from sql_agent.storage.db import StorageBackend
from sql_agent.storage.vector import VectorBackend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sql-agent"])


# ─── 请求 / 响应模型 ─────────────────────────────────────


class QuestionRequest(BaseModel):
    question: str
    db_connection_id: str
    schemas: Optional[List[str]] = None
    conversation_id: Optional[str] = None
    enable_correction: bool = True
    agent_mode: str = "auto"


class SQLResponse(BaseModel):
    answer: Optional[str] = None
    sql: str
    status: str
    confidence_score: Optional[float] = None
    agent_state: Optional[Dict[str, Any]] = None
    recovery: Optional[Dict[str, Any]] = None
    semantic_plan: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    visualization: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    intermediate_steps: Optional[List[Dict[str, str]]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class DBConnectionRequest(BaseModel):
    alias: str
    connection_uri: str
    schemas: Optional[List[str]] = None
    llm_api_key: Optional[str] = None


class GoldenSQLRequest(BaseModel):
    prompt_text: str
    sql: str
    db_connection_id: str


class FeedbackRequest(BaseModel):
    question: str
    db_connection_id: str
    sql: str
    answer_correct: bool
    sql_correct: bool
    wrong_reason: Optional[str] = None
    corrected_sql: Optional[str] = None
    comment: Optional[str] = None


_system: Optional[System] = None
_conversation_manager: Optional[Any] = None


def create_system() -> System:
    """创建已配置的系统实例"""
    global _system
    if _system is None:
        settings = Settings()
        _system = System(settings)
    return _system


def reset_system() -> None:
    """重置全局依赖，供测试和本地热重载使用"""
    global _system, _conversation_manager
    if _system is not None:
        _system.stop()
    _system = None
    _conversation_manager = None


def get_conversation_manager(storage: Any):
    """获取带存储后端的对话管理器"""
    global _conversation_manager
    if _conversation_manager is None:
        from sql_agent.context.conversation import ConversationManager

        _conversation_manager = ConversationManager(storage=storage)
    return _conversation_manager


# ─── 健康检查 ───────────────────────────────────────────


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "sql-agent"}


# ─── 问题 → SQL ─────────────────────────────────────────


@router.post("/question", response_model=SQLResponse)
async def ask_question(request: QuestionRequest):
    """
    提交自然语言问题并获取 SQL。
    支持通过 conversation_id 进行多轮对话。
    """
    system = create_system()
    try:
        runtime_result = QuestionRuntime(system, get_conversation_manager).run(request)
        result = runtime_result.agent_result
        analysis = runtime_result.analysis
        semantic_plan = runtime_result.semantic_plan

        return SQLResponse(
            answer=analysis.answer if analysis else None,
            sql=result.sql or "",
            status=result.status,
            confidence_score=runtime_result.confidence_score,
            agent_state=runtime_result.state.to_dict(),
            recovery=runtime_result.recovery.to_dict(),
            semantic_plan=semantic_plan.to_dict() if semantic_plan else None,
            result=analysis.result.__dict__ if analysis else None,
            analysis=(
                {
                    "summary": analysis.summary,
                    "key_findings": [
                        {
                            "claim": finding.claim,
                            "evidence": finding.evidence,
                            "finding_type": finding.finding_type,
                        }
                        for finding in analysis.key_findings
                    ],
                    "limitations": analysis.limitations,
                    "followup_questions": analysis.followup_questions,
                }
                if analysis
                else None
            ),
            visualization=analysis.visualization if analysis else None,
            conversation_id=runtime_result.state.conversation_id,
            intermediate_steps=runtime_result.intermediate_steps,
            candidates=[candidate.to_dict() for candidate in runtime_result.ranked_candidates],
            error=result.error,
        )

    except DatabaseConnectionNotFound:
        raise HTTPException(status_code=404, detail="Database connection not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Question processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Golden SQL 管理 ────────────────────────────────────


@router.post("/golden-sqls")
async def add_golden_sql(request: GoldenSQLRequest):
    """添加用于 few-shot 检索的 Golden SQL 示例"""
    system = create_system()
    storage = system.instance(StorageBackend)
    vector = system.instance(VectorBackend)

    record = GoldenSQL(
        prompt_text=request.prompt_text,
        sql=request.sql,
        db_connection_id=request.db_connection_id,
    )
    id = storage.insert("golden_sqls", record.__dict__)
    record.id = id
    vector.add_records([record], "golden_sqls")

    return {"id": id, "status": "created"}


@router.get("/golden-sqls")
async def list_golden_sqls(db_connection_id: str = Query(None)):
    """列出 Golden SQL 示例"""
    system = create_system()
    storage = system.instance(StorageBackend)
    query = {}
    if db_connection_id:
        query["db_connection_id"] = db_connection_id
    return storage.find("golden_sqls", query)


# ─── 查询反馈 / Verified Query ───────────────────────────


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交查询反馈，必要时沉淀为 verified query"""
    from sql_agent.feedback.service import FeedbackService
    from sql_agent.feedback.types import QueryFeedback

    system = create_system()
    storage = system.instance(StorageBackend)
    feedback_id = FeedbackService(storage).submit_feedback(
        QueryFeedback(
            question=request.question,
            db_connection_id=request.db_connection_id,
            sql=request.sql,
            answer_correct=request.answer_correct,
            sql_correct=request.sql_correct,
            wrong_reason=request.wrong_reason,
            corrected_sql=request.corrected_sql,
            comment=request.comment,
        )
    )
    return {"id": feedback_id, "status": "created"}


@router.get("/feedback")
async def list_feedback(db_connection_id: str):
    """查询某个数据库连接下的用户反馈"""
    from sql_agent.feedback.service import FeedbackService

    system = create_system()
    storage = system.instance(StorageBackend)
    return [item.to_dict() for item in FeedbackService(storage).list_feedback(db_connection_id)]


@router.get("/verified-queries")
async def list_verified_queries(db_connection_id: str):
    """查询某个数据库连接下沉淀出的 verified queries"""
    from sql_agent.feedback.service import FeedbackService

    system = create_system()
    storage = system.instance(StorageBackend)
    return [
        item.to_dict() for item in FeedbackService(storage).list_verified_queries(db_connection_id)
    ]


# ─── 数据库连接管理 ─────────────────────────────────────


@router.post("/database-connections")
async def create_database_connection(request: DBConnectionRequest):
    """注册新的数据库连接"""
    system = create_system()
    storage = system.instance(StorageBackend)
    conn = DatabaseConnection(
        alias=request.alias,
        connection_uri=request.connection_uri,
        schemas=request.schemas,
        llm_api_key=request.llm_api_key,
    )
    id = storage.insert("db_connections", conn.__dict__)
    storage.update("db_connections", {"id": id}, {"id": id})
    return {"id": id, "alias": request.alias}


@router.get("/database-connections")
async def list_database_connections():
    """列出所有数据库连接"""
    system = create_system()
    storage = system.instance(StorageBackend)
    return storage.find("db_connections", {})


# ─── Schema / 表描述 ────────────────────────────────────


@router.post("/database-connections/{db_id}/scan")
async def scan_database(db_id: str, background_tasks: BackgroundTasks):
    """扫描数据库 schema"""
    system = create_system()
    storage = system.instance(StorageBackend)
    db_conn_data = storage.find_one("db_connections", {"id": db_id})
    if not db_conn_data:
        raise HTTPException(status_code=404, detail="Database connection not found")

    db_conn = DatabaseConnection(**db_conn_data)
    database = SQLDatabase.get_sql_engine(db_conn)
    scanner = SchemaScanner(database)
    tables = scanner.scan_all_tables(db_id)

    for table in tables:
        storage.insert("table_descriptions", table.__dict__)

    return {"tables_scanned": len(tables)}


@router.get("/table-descriptions/{db_id}")
async def list_table_descriptions(db_id: str):
    """获取指定数据库的表描述"""
    system = create_system()
    storage = system.instance(StorageBackend)
    return storage.find("table_descriptions", {"db_connection_id": db_id})


# ─── 对话管理 ───────────────────────────────────────────


@router.get("/conversations")
async def list_conversations():
    """列出活跃对话"""
    system = create_system()
    storage = system.instance(StorageBackend)
    conv_mgr = get_conversation_manager(storage)
    return {"conversations": [conv.id for conv in conv_mgr.list_active_conversations()]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    system = create_system()
    storage = system.instance(StorageBackend)
    conv_mgr = get_conversation_manager(storage)
    if conv_mgr.delete_conversation(conversation_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")
