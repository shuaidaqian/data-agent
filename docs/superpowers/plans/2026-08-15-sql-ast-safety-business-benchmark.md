# SQL AST Safety And Business Benchmark Implementation Plan

> 历史计划说明：本文记录 2026-08-15 SQL AST safety 和 business benchmark 的实施计划。当前项目已经在此基础上继续加入 QuestionRuntime / AgentState、ToolRegistry 和 RecoveryLoop。最新实现以 `README.md`、`docs/project-highlights.md` 和最新 `docs/iterations/` 记录为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加基于 `sqlglot` 的 SQL AST 安全校验，并构造可复现的 SQLite 企业经营分析 benchmark 数据集与 40 条评估用例。

**Architecture:** 新增 `sql_agent/security/` 作为统一 SQL 安全策略层，由 `AgentToolkit` 和 `CandidateRanker` 共同调用；新增 `sql_agent/eval/demo_business.py` 构造 business demo SQLite，配套 `eval_cases/business_semantic_model.yml` 和 `eval_cases/business_benchmark.yml`。Evaluation Harness 扩展少量 expected fields，让 benchmark 能校验列、行数、任意行和难度指标。

**Tech Stack:** Python dataclass、SQLAlchemy/SQLite、PyYAML、sqlglot、pytest。

---

### Task 1: SQL AST Safety Validator

**Files:**
- Create: `sql_agent/security/types.py`
- Create: `sql_agent/security/policy.py`
- Create: `sql_agent/security/sql_safety.py`
- Create: `tests/test_sql_ast_safety.py`
- Modify: `requirements.txt`

- [x] Write failing tests for SELECT-only、alias、CTE、subquery、unknown table、unknown column、multi statement、ambiguous column、SELECT star policy。
- [x] Implement `SQLSafetyPolicy`、`SQLSafetyReport`、`SQLSafetyValidator` with `sqlglot` AST traversal.
- [x] Run `pytest tests/test_sql_ast_safety.py -q` until green.

### Task 2: Integrate Safety Validator

**Files:**
- Modify: `sql_agent/agent/tools.py`
- Modify: `sql_agent/ranking/candidate.py`
- Modify: `sql_agent/ranking/ranker.py`
- Modify: `tests/test_agent_tools.py`
- Modify: `tests/test_candidate_ranking.py`

- [x] Replace duplicated parser/regex validation in tool and ranker paths with `SQLSafetyValidator`.
- [x] Add `safety` payload to `SQLCandidate`.
- [x] Keep existing public behavior and error Chinese messages compatible.
- [x] Run affected tests.

### Task 3: Business Benchmark Dataset

**Files:**
- Create: `sql_agent/eval/demo_business.py`
- Create: `eval_cases/business_semantic_model.yml`
- Create: `eval_cases/business_benchmark.yml`
- Create: `eval_cases/README.md`
- Create: `tests/test_business_benchmark_dataset.py`

- [x] Build deterministic SQLite tables: departments、employees、customers、products、orders、order_items、refunds、web_events。
- [x] Write semantic model with metrics/dimensions/relationships for GMV、paid_order_count、refund_amount、refund_rate、active_customer_count。
- [x] Write 40 benchmark cases covering basic、semantic、join、trend、analysis、visualization、safety tags.
- [x] Validate case id uniqueness, tags, expected fields, semantic model loading, and selected golden SQL execution.

### Task 4: Evaluation Harness Extension

**Files:**
- Modify: `sql_agent/eval/harness.py`
- Modify: `tests/test_eval_benchmark_2.py`

- [x] Add expected fields: `expected_status`、`expected_columns`、`expected_row_count`、`expected_any_row`、`forbidden_sql_contains`、`difficulty`、`golden_sql`。
- [x] Add difficulty metrics.
- [ ] Add failed case markdown details.
- [x] Keep existing harness tests compatible.

### Task 5: Verification And Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/project-highlights.md`
- Modify: `docs/interview-prep-sql-agent.md`
- Add iteration record under `docs/iterations/`.

- [ ] Run `python -m black sql_agent tests main.py`.
- [ ] Run `python -m ruff check sql_agent tests main.py`.
- [ ] Run `pytest tests -q`.
- [ ] Run `python -m compileall -q sql_agent tests main.py`.
- [ ] Document benchmark running commands and current boundary.
