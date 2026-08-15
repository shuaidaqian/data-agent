"""问题问答 Runtime 编排。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sql_agent.agent.agent_selector import AgentSelector
from sql_agent.agent.base import AgentResult
from sql_agent.analysis.types import AnalysisResult
from sql_agent.core.config import System
from sql_agent.core.types import AgentConfig, DatabaseConnection, LLMConfig, Prompt
from sql_agent.ranking.candidate import SQLCandidate
from sql_agent.runtime.recovery import RecoveryDecision, RecoveryLoop
from sql_agent.runtime.state import AgentStage, AgentState, AgentStatus
from sql_agent.sql.database import SQLDatabase
from sql_agent.sql.scanner import SchemaScanner

logger = logging.getLogger(__name__)


class DatabaseConnectionNotFound(Exception):
    """数据库连接不存在。"""


@dataclass
class QuestionRuntimeResult:
    """Runtime 对路由层返回的完整问答产物。"""

    state: AgentState
    agent_result: AgentResult
    confidence_score: Optional[float] = None
    analysis: Optional[AnalysisResult] = None
    recovery: RecoveryDecision = field(default_factory=RecoveryDecision)
    ranked_candidates: List[SQLCandidate] = field(default_factory=list)
    semantic_plan: Any = None
    intermediate_steps: List[Dict[str, str]] = field(default_factory=list)


class QuestionRuntime:
    """将一次自然语言数据问答编排为受控状态机。"""

    def __init__(
        self,
        system: System,
        conversation_manager_factory: Callable[[Any], Any],
    ):
        self.system = system
        self.conversation_manager_factory = conversation_manager_factory

    def run(self, request: Any) -> QuestionRuntimeResult:
        """执行一次问答 Runtime。"""
        state = AgentState(
            question=request.question,
            db_connection_id=request.db_connection_id,
            conversation_id=request.conversation_id,
        )
        result = AgentResult()
        recovery = RecoveryDecision()
        confidence_score = None
        analysis = None
        ranked_candidates: List[SQLCandidate] = []
        steps: List[Dict[str, str]] = []

        try:
            deps = self._load_dependencies()
            llm = deps["llm"]
            storage = deps["storage"]
            context_store = deps["context_store"]
            evaluator = deps["evaluator"]

            state.transition_to(AgentStage.LOAD_CONTEXT)
            conv_mgr = self.conversation_manager_factory(storage)
            conversation = conv_mgr.get_or_create(
                request.conversation_id,
                request.db_connection_id,
            )
            state.conversation = conversation
            state.conversation_id = conversation.id

            prompt = Prompt(
                text=request.question,
                db_connection_id=request.db_connection_id,
                schemas=request.schemas,
            )
            state.prompt = prompt

            db_conn = self._load_database_connection(storage, request.db_connection_id)
            state.database_connection = db_conn
            database = SQLDatabase.get_sql_engine(db_conn)
            table_descriptions = SchemaScanner(database).scan_all_tables(request.db_connection_id)
            state.table_descriptions = table_descriptions

            few_shot, instructions = context_store.retrieve_context_for_question(prompt)

            state.transition_to(AgentStage.PLAN_QUERY)
            semantic_plan, semantic_candidate_sqls = self._create_semantic_plan(request.question)
            state.semantic_plan = semantic_plan
            state.semantic_candidate_sqls = semantic_candidate_sqls

            state.transition_to(AgentStage.GENERATE_SQL)
            agent_config = AgentConfig(
                mode=request.agent_mode,
                enable_self_correction=request.enable_correction,
            )
            result = AgentSelector(self.system, LLMConfig(), agent_config).generate_sql(
                prompt=prompt,
                database_connection=db_conn,
                table_descriptions=table_descriptions,
                conversation=conversation,
                few_shot_examples=few_shot,
                instructions=instructions,
            )
            result = self._maybe_correct_sql(request, result, llm, database, table_descriptions)
            state.agent_result = result
            steps, candidate_step_texts = self._extract_steps(result)
            state.intermediate_steps = steps

            state.transition_to(AgentStage.RANK_CANDIDATES)
            if result.sql:
                ranked_candidates = self._rank_candidates(
                    request=request,
                    result=result,
                    candidate_step_texts=candidate_step_texts,
                    semantic_candidate_sqls=semantic_candidate_sqls,
                    semantic_plan=semantic_plan,
                    storage=storage,
                    database=database,
                    table_descriptions=table_descriptions,
                    evaluator=evaluator,
                )
                state.ranked_candidates = ranked_candidates
                recovery = RecoveryLoop().recover(ranked_candidates)
                state.recovery_attempts = recovery.recovery_attempts
                if recovery.attempted:
                    state.transition_to(AgentStage.RECOVER)
                if recovery.selected_candidate:
                    result.sql = recovery.selected_candidate.sql
                    result.status = recovery.selected_candidate.status
                    confidence_score = recovery.selected_candidate.score
                    state.selected_candidate = recovery.selected_candidate
                elif ranked_candidates:
                    result.sql = ranked_candidates[0].sql
                    result.status = ranked_candidates[0].status
                    confidence_score = ranked_candidates[0].score
                    result.error = recovery.reason
                    state.fail(recovery.reason)
                else:
                    confidence_score = evaluator.evaluate(result.sql, request.question)

            if state.selected_candidate and state.selected_candidate.status == "VALID":
                state.transition_to(AgentStage.ANALYZE_RESULT)
                analysis = self._create_result_analyzer(llm).analyze(
                    request.question,
                    state.selected_candidate,
                )
                state.analysis = analysis

            self._save_conversation(conv_mgr, conversation, request.question, result, steps)
            if state.status != AgentStatus.FAILED:
                state.transition_to(AgentStage.FINALIZE, status=AgentStatus.SUCCEEDED)
            return QuestionRuntimeResult(
                state=state,
                agent_result=result,
                confidence_score=confidence_score,
                analysis=analysis,
                recovery=recovery,
                ranked_candidates=ranked_candidates,
                semantic_plan=semantic_plan,
                intermediate_steps=steps,
            )
        except DatabaseConnectionNotFound:
            state.fail("Database connection not found")
            raise
        except Exception as exc:
            state.fail(str(exc))
            raise

    def _load_dependencies(self) -> Dict[str, Any]:
        from sql_agent.context.base import ContextStore
        from sql_agent.eval.evaluator import Evaluator
        from sql_agent.llm.base import LLMBackend
        from sql_agent.storage.db import StorageBackend
        from sql_agent.storage.vector import VectorBackend

        llm = self.system.instance(LLMBackend)
        storage = self.system.instance(StorageBackend)
        self.system.instance(VectorBackend)
        context_store = self.system.instance(ContextStore)
        evaluator = self.system.instance(Evaluator)
        return {
            "llm": llm,
            "storage": storage,
            "context_store": context_store,
            "evaluator": evaluator,
        }

    def _load_database_connection(self, storage: Any, db_connection_id: str) -> DatabaseConnection:
        db_conn_data = storage.find_one("db_connections", {"id": db_connection_id})
        if not db_conn_data:
            raise DatabaseConnectionNotFound()
        allowed = DatabaseConnection.__dataclass_fields__
        return DatabaseConnection(
            **{key: value for key, value in db_conn_data.items() if key in allowed}
        )

    def _create_semantic_plan(self, question: str):
        if not self.system.settings.semantic_model_path:
            return None, []

        from sql_agent.semantic.compiler import SemanticSQLCompiler
        from sql_agent.semantic.planner import SemanticPlanner
        from sql_agent.semantic.registry import SemanticModelRegistry
        from sql_agent.semantic.validator import SemanticPlanValidator

        model_path = Path(self.system.settings.semantic_model_path)
        if not model_path.exists():
            return None, []

        registry = SemanticModelRegistry.from_yaml(model_path)
        plan = SemanticPlanner(registry).plan(question)
        validation = SemanticPlanValidator(registry).validate(plan)
        if not validation.valid or not plan.metrics:
            return plan, []
        sql = SemanticSQLCompiler(registry).compile(plan)
        return plan, [sql] if sql else []

    def _maybe_correct_sql(
        self,
        request: Any,
        result: AgentResult,
        llm: Any,
        database: SQLDatabase,
        table_descriptions: List[Any],
    ) -> AgentResult:
        if not (
            request.enable_correction and self.system.settings.enable_self_correction and result.sql
        ):
            return result

        from sql_agent.correction.dail_style import DAILStyleCorrector

        schema_info = "\n".join(t.table_schema for t in table_descriptions[:5])
        corr_result = DAILStyleCorrector(llm, database, max_rounds=3).correct(
            question=request.question,
            sql=result.sql,
            schema_info=schema_info,
            error=result.error,
        )
        if corr_result.status == "VALID":
            result.sql = corr_result.sql
            result.status = "CORRECTED"
        return result

    def _extract_steps(self, result: AgentResult):
        steps = []
        candidate_step_texts = []
        for step in getattr(result, "steps", []):
            candidate_step_texts.extend([step.action_input, step.observation])
            steps.append(
                {
                    "thought": step.thought,
                    "action": step.action,
                    "observation": step.observation[:200] if step.observation else "",
                }
            )
        return steps, candidate_step_texts

    def _rank_candidates(
        self,
        request: Any,
        result: AgentResult,
        candidate_step_texts: List[str],
        semantic_candidate_sqls: List[str],
        semantic_plan: Any,
        storage: Any,
        database: SQLDatabase,
        table_descriptions: List[Any],
        evaluator: Any,
    ) -> List[SQLCandidate]:
        from sql_agent.feedback.service import FeedbackService
        from sql_agent.ranking.generator import CandidateGenerator
        from sql_agent.ranking.ranker import CandidateRanker

        candidate_sqls = CandidateGenerator.collect(result.sql, candidate_step_texts)
        candidate_sqls = [*semantic_candidate_sqls, *candidate_sqls]
        verified_sqls = []
        try:
            verified_matches = FeedbackService(storage).retrieve_verified_queries(
                request.question,
                request.db_connection_id,
            )
            verified_sqls = [match.sql for match in verified_matches]
            candidate_sqls = [match.sql for match in verified_matches] + candidate_sqls
        except Exception:
            logger.debug("Verified query retrieval skipped", exc_info=True)

        return CandidateRanker(
            database=database,
            table_descriptions=table_descriptions,
            evaluator=evaluator,
            semantic_plan=semantic_plan,
            verified_sqls=verified_sqls,
        ).rank(request.question, candidate_sqls)

    def _create_result_analyzer(self, llm: Any):
        from sql_agent.analysis.result_analyzer import HeuristicResultAnalyzer, LLMResultAnalyzer

        if self.system.settings.result_analyzer == "llm":
            return LLMResultAnalyzer(llm)
        return HeuristicResultAnalyzer()

    def _save_conversation(
        self,
        conv_mgr: Any,
        conversation: Any,
        question: str,
        result: AgentResult,
        steps: List[Dict[str, str]],
    ) -> None:
        conv_mgr.add_turn(conversation, "user", question)
        conv_mgr.add_turn(
            conversation,
            "assistant",
            result.sql or "",
            sql=result.sql,
            sql_result=str(steps[:2]),
        )
