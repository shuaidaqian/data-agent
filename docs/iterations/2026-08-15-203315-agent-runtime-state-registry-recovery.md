# 2026-08-15 20:33:15 Agent Runtime State Registry Recovery

## 本次目标

本次迭代补齐 Agent Framework 层的三个关键能力：

- `AgentState`：把一次 `/api/v1/question` 问答变成可追踪状态机。
- `ToolRegistry`：把 Agent 工具从硬编码列表升级为声明式注册。
- `RecoveryLoop`：当最佳候选 SQL 失败时，基于执行证据选择可恢复候选，而不是直接返回失败。

本次明确不做完整 trace，不引入 LangGraph。设计目标是先把企业 Data Agent 的受控 Runtime 边界抽出来，后续如果需要 checkpoint、human-in-the-loop 或复杂图编排，可以把 Runtime 节点映射到 LangGraph。

## 完成内容

### 1. AgentState 状态机

新增 `sql_agent/runtime/state.py`：

- `AgentStage`
  - `INIT`
  - `LOAD_CONTEXT`
  - `PLAN_QUERY`
  - `GENERATE_SQL`
  - `RANK_CANDIDATES`
  - `RECOVER`
  - `ANALYZE_RESULT`
  - `FINALIZE`
  - `FAILED`
- `AgentStatus`
  - `RUNNING`
  - `SUCCEEDED`
  - `FAILED`
- `AgentState`
  - 保存 question、db_connection_id、conversation_id、当前阶段、状态、恢复次数、错误和关键中间产物。
  - 提供 `transition_to()`、`fail()` 和 `to_dict()`。

API 现在会返回轻量 `agent_state` 字段，用于说明一次问答运行到哪个阶段、是否成功、是否发生恢复。

### 2. Tool Registry 声明式工具注册

新增 `sql_agent/runtime/tool_registry.py`：

- `ToolSpec`
  - `name`
  - `description`
  - `fn`
  - `parameters`
  - `category`
  - `permission_scope`
  - `requires_sql_safety`
  - `timeout_ms`
- `ToolRegistry`
  - 注册工具。
  - 拒绝重复工具名。
  - 导出兼容旧 Agent 的 `ToolDef`。

`AgentToolkit` 现在通过 `_build_tool_registry()` 注册工具，再通过 `as_tool_defs()` 返回给现有 ReAct / Plan-and-Solve Agent 使用。

这样做保留了现有 Agent 接口，同时让工具具备权限、安全和参数元数据，为后续工具治理和 UI 展示留出扩展点。

### 3. Recovery Loop 失败恢复

新增 `sql_agent/runtime/recovery.py`：

- `RecoveryDecision`
  - `attempted`
  - `recovered`
  - `reason`
  - `selected_candidate`
  - `recovery_attempts`
- `RecoveryLoop`
  - 如果排序第一的候选已经可用，则不进入恢复。
  - 如果最佳候选失败，则选择后续第一个真实执行成功的候选。
  - 如果所有候选均失败，则返回结构化失败原因。

这让系统具备最基础的 Agent 行为闭环：

```text
观察候选失败 -> 选择替代候选 -> 基于可执行候选继续分析
```

### 4. QuestionRuntime 路由编排下沉

新增 `sql_agent/runtime/question_runtime.py`：

- `/api/v1/question` 的核心编排迁移到 `QuestionRuntime.run()`。
- 路由层只负责 HTTP 请求、异常映射和响应组装。
- Runtime 负责：
  - 加载 LLM / Storage / Vector / ContextStore / Evaluator。
  - 创建和恢复 Conversation。
  - 从存储读取真实数据库连接。
  - 扫描 schema。
  - 生成 SemanticQueryPlan。
  - 调用 AgentSelector。
  - 执行 DAIL 修正。
  - 收集候选 SQL。
  - 调用 CandidateRanker。
  - 调用 RecoveryLoop。
  - 调用 ResultAnalyzer。
  - 写入对话历史。

API 响应新增：

- `agent_state`
- `recovery`

原有字段 `answer`、`sql`、`status`、`result`、`analysis`、`visualization`、`conversation_id`、`intermediate_steps`、`candidates` 保持兼容。

## 实现效果

本次迭代后，项目在面试表达上更像一个受控 Data Agent Runtime，而不只是 SQL 工具集合：

1. **一次请求有生命周期。**
   可以说明请求从加载上下文、语义规划、SQL 生成、候选排序、失败恢复到结果分析的阶段推进。

2. **工具不是散落的函数列表。**
   每个工具有声明式元数据，后续可以继续接权限、审计、UI 展示和工具治理。

3. **失败不是直接返回。**
   当最佳候选失败时，系统会基于执行证据选择可执行候选；全部失败时返回结构化原因。

4. **路由层更干净。**
   `/api/v1/question` 不再堆叠大量业务编排逻辑，核心链路集中在 `QuestionRuntime`。

## 测试记录

本次采用 TDD：

1. 先新增失败测试：
   - `tests/test_agent_state.py`
   - `tests/test_tool_registry.py`
   - `tests/test_recovery_loop.py`
   - `tests/test_api_e2e.py` 中补充 `agent_state` / `recovery` 断言
2. 首次运行失败原因为 `sql_agent.runtime` 模块不存在，符合预期。
3. 实现 Runtime 后，新增测试转绿。

已执行的局部验证：

```bash
pytest tests/test_agent_state.py tests/test_tool_registry.py tests/test_recovery_loop.py tests/test_api_e2e.py::test_sqlite_mockllm_question_endpoint_uses_stored_connection_and_keeps_history -q
pytest tests/test_api_e2e.py tests/test_agent_tools.py tests/test_agent_base.py -q
pytest tests/test_candidate_ranking.py tests/test_candidate_ranking_2.py tests/test_sql_ast_safety.py -q
```

结果：

```text
8 passed, 2 warnings
27 passed, 2 warnings
10 passed, 1 warning
```

最终全量验证结果以本次提交前最新命令输出为准。

本次最终验证命令：

```bash
python -m black sql_agent tests main.py
python -m ruff check sql_agent tests main.py
pytest tests -q
python -m compileall -q sql_agent tests main.py
git diff --check
```

结果：

```text
black: 1 file reformatted, 98 files left unchanged
ruff: All checks passed
pytest tests -q: 141 passed, 3 skipped, 2 warnings
compileall: passed
git diff --check: passed
```

说明：

- 3 个 skipped 仍是真实 OpenAI、MongoDB、ChromaDB 集成测试，需要显式外部环境才运行。
- warnings 仍来自 FastAPI TestClient/httpx/starlette 依赖弃用提示和当前工作区 `.pytest_cache` 写入权限提示，不影响断言。
- `git diff --check` 只提示 Windows 行尾转换 warning，没有尾随空白错误。

## 涉及文件

- `sql_agent/runtime/__init__.py`
- `sql_agent/runtime/state.py`
- `sql_agent/runtime/tool_registry.py`
- `sql_agent/runtime/recovery.py`
- `sql_agent/runtime/question_runtime.py`
- `sql_agent/agent/tools.py`
- `sql_agent/api/routes.py`
- `tests/test_agent_state.py`
- `tests/test_tool_registry.py`
- `tests/test_recovery_loop.py`
- `tests/test_api_e2e.py`
- `README.md`
- `docs/project-highlights.md`
