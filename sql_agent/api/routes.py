"""
FastAPI route definitions.

Exposes REST API endpoints for NL-to-SQL functionality.
Designed to be a drop-in replacement for Dataherald's API layer.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from sql_agent.core.config import Settings, System
from sql_agent.core.types import (
     AgentConfig,
     DatabaseConnection,
     GoldenSQL,
     LLMConfig,
     Prompt,
)
from sql_agent.storage.db import StorageBackend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sql-agent"])


# ─── Request/Response Models ─────────────────────────────

class QuestionRequest(BaseModel):
     question: str
     db_connection_id: str
     schemas: Optional[List[str]] = None
     conversation_id: Optional[str] = None
     enable_correction: bool = True
     agent_mode: str = "auto"


class SQLResponse(BaseModel):
     sql: str
     status: str
     confidence_score: Optional[float] = None
     conversation_id: Optional[str] = None
     intermediate_steps: Optional[List[Dict[str, str]]] = None
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


_system: Optional[System] = None
_conversation_manager: Optional[Any] = None


def create_system() -> System:
     """Create a configured system instance"""
     global _system
     if _system is None:
         settings = Settings()
         _system = System(settings)
     return _system


def reset_system() -> None:
     """Reset global dependencies for tests and local reloads"""
     global _system, _conversation_manager
     if _system is not None:
         _system.stop()
     _system = None
     _conversation_manager = None


def get_conversation_manager(storage: Any):
     """Get a storage-backed conversation manager"""
     global _conversation_manager
     if _conversation_manager is None:
         from sql_agent.context.conversation import ConversationManager
         _conversation_manager = ConversationManager(storage=storage)
     return _conversation_manager


# ─── Health Check ─────────────────────────────────────────

@router.get("/health")
async def health_check():
     return {"status": "ok", "service": "sql-agent"}


# ─── Question → SQL ──────────────────────────────────────

@router.post("/question", response_model=SQLResponse)
async def ask_question(request: QuestionRequest):
     """
     Ask a natural language question and get SQL.
     Supports multi-turn conversation via conversation_id.
     """
     system = create_system()
     try:
         from sql_agent.agent.agent_selector import AgentSelector
         from sql_agent.context.base import ContextStore
         from sql_agent.correction.dail_style import DAILStyleCorrector
         from sql_agent.eval.evaluator import Evaluator
         from sql_agent.llm.base import LLMBackend
         from sql_agent.sql.database import SQLDatabase
         from sql_agent.sql.scanner import SchemaScanner
         from sql_agent.storage.db import StorageBackend
         from sql_agent.storage.vector import VectorBackend

         llm = system.instance(LLMBackend)
         storage = system.instance(StorageBackend)
         system.instance(VectorBackend)
         context_store = system.instance(ContextStore)
         evaluator = system.instance(Evaluator)

         # Conversation management
         conv_mgr = get_conversation_manager(storage)
         conversation = conv_mgr.get_or_create(
             request.conversation_id,
             request.db_connection_id,
         )

         # Create prompt
         prompt = Prompt(
             text=request.question,
             db_connection_id=request.db_connection_id,
             schemas=request.schemas,
         )

         # Get database and schema
         db_conn_data = storage.find_one("db_connections", {"id": request.db_connection_id})
         if not db_conn_data:
             raise HTTPException(status_code=404, detail="Database connection not found")
         db_conn = DatabaseConnection(**{
             key: value for key, value in db_conn_data.items()
             if key in DatabaseConnection.__dataclass_fields__
         })
         database = SQLDatabase.get_sql_engine(db_conn)
         scanner = SchemaScanner(database)
         table_descriptions = scanner.scan_all_tables(request.db_connection_id)

         # Get context (few-shot + instructions)
         few_shot, instructions = context_store.retrieve_context_for_question(prompt)

         # Select and run agent
         agent_config = AgentConfig(
             mode=request.agent_mode,
             enable_self_correction=request.enable_correction,
         )
         selector = AgentSelector(system, LLMConfig(), agent_config)
         result = selector.generate_sql(
             prompt=prompt,
             database_connection=db_conn,
             table_descriptions=table_descriptions,
             conversation=conversation,
             few_shot_examples=few_shot,
             instructions=instructions,
         )

         # Self-correction
         if request.enable_correction and system.settings.enable_self_correction and result.sql:
             schema_info = "\n".join(t.table_schema for t in table_descriptions[:5])
             corrector = DAILStyleCorrector(llm, database, max_rounds=3)
             corr_result = corrector.correct(
                 question=request.question,
                 sql=result.sql,
                 schema_info=schema_info,
                 error=result.error,
             )
             if corr_result.status == "VALID":
                 result.sql = corr_result.sql
                 result.status = "CORRECTED"

         confidence_score = None
         if result.sql:
             confidence_score = evaluator.evaluate(result.sql, request.question)

         # Extract intermediate steps
         steps = []
         for step in getattr(result, "steps", []):
             steps.append({
                 "thought": step.thought,
                 "action": step.action,
                 "observation": step.observation[:200] if step.observation else "",
             })

         # Save to conversation
         conv_mgr.add_turn(
             conversation, "user", request.question
         )
         conv_mgr.add_turn(
             conversation, "assistant", result.sql or "",
             sql=result.sql,
             sql_result=str(steps[:2]),
         )

         return SQLResponse(
             sql=result.sql or "",
             status=result.status,
             confidence_score=confidence_score,
             conversation_id=conversation.id,
             intermediate_steps=steps,
             error=result.error,
         )

     except HTTPException:
         raise
     except Exception as e:
         logger.error(f"Question processing failed: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=str(e))


# ─── Golden SQL Management ───────────────────────────────

@router.post("/golden-sqls")
async def add_golden_sql(request: GoldenSQLRequest):
     """Add a golden SQL example for few-shot retrieval"""
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
     """List golden SQL examples"""
     system = create_system()
     storage = system.instance(StorageBackend)
     query = {}
     if db_connection_id:
         query["db_connection_id"] = db_connection_id
     return storage.find("golden_sqls", query)


# ─── Database Connection Management ──────────────────────

@router.post("/database-connections")
async def create_database_connection(request: DBConnectionRequest):
     """Register a new database connection"""
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
     """List all database connections"""
     system = create_system()
     storage = system.instance(StorageBackend)
     return storage.find("db_connections", {})


# ─── Schema / Table Descriptions ──────────────────────────

@router.post("/database-connections/{db_id}/scan")
async def scan_database(db_id: str, background_tasks: BackgroundTasks):
     """Scan database schema"""
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
     """Get table descriptions for a database"""
     system = create_system()
     storage = system.instance(StorageBackend)
     return storage.find("table_descriptions", {"db_connection_id": db_id})


# ─── Conversation Management ─────────────────────────────

@router.get("/conversations")
async def list_conversations():
     """List active conversations"""
     system = create_system()
     storage = system.instance(StorageBackend)
     conv_mgr = get_conversation_manager(storage)
     return {"conversations": [conv.id for conv in conv_mgr.list_active_conversations()]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
     """Delete a conversation"""
     system = create_system()
     storage = system.instance(StorageBackend)
     conv_mgr = get_conversation_manager(storage)
     if conv_mgr.delete_conversation(conversation_id):
         return {"status": "deleted"}
     raise HTTPException(status_code=404, detail="Conversation not found")
