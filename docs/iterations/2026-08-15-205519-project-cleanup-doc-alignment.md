# 2026-08-15 20:55:19 Project Cleanup And Documentation Alignment

## 本次目标

本次迭代对全项目代码和文档做一次收敛清理：

- 代码保持干净整洁，清理路由层冗余编排和状态边界问题。
- 文档全部对齐最新实现，避免 README、面试材料、学习计划和历史计划之间互相矛盾。
- 保留原型项目的真实边界，不把当前系统包装成完整生产平台。

## 清理原则

1. **不删除有效能力。**
   保留 Semantic Layer、SQL AST safety、SQLite business benchmark、CandidateRanker、ResultAnalyzer、Visualization、Feedback、Evaluation 和真实 adapter。

2. **当前说明文档必须对齐最新实现。**
   README、项目亮点、面试准备、学习资料和架构说明都要体现 QuestionRuntime / AgentState、ToolRegistry 和 RecoveryLoop。

3. **历史记录保留事实，但标明历史状态。**
   对旧计划和旧迭代记录只加历史说明或局部修正，不把当时计划改写成现在事实。

4. **代码只做必要清理。**
   避免为了“整理”做大规模重构，优先保证测试稳定和职责边界清晰。

## 代码清理

### 1. Runtime 不可恢复状态修正

修正 `QuestionRuntime` 中候选不可恢复时的状态边界：

- 当所有候选都无法通过安全校验或执行验证时，API 仍返回结构化响应。
- `agent_state.stage` 标记为 `FAILED`。
- `agent_state.status` 标记为 `FAILED`。
- `recovery.recovered` 返回 `false`。
- `SQLResponse.error` 返回明确的不可恢复原因。

这避免了“业务上已经失败，但状态摘要仍显示成功”的不一致。

### 2. 测试假件补充

新增 `UnsafeSQLMockLLM`，用于稳定模拟模型生成危险 SQL 的场景。

新增 API E2E 断言：

- 候选全部不可恢复时不返回 500。
- 状态机进入 `FAILED`。
- 恢复环路给出结构化失败原因。

### 3. 路由层保持轻量

`/api/v1/question` 的核心编排已经集中到 `QuestionRuntime`，路由层只负责：

- 接收请求。
- 调用 Runtime。
- 组装响应。
- 映射 HTTP 异常。

## 文档更新

### 1. README

更新内容：

- 主链路加入 `QuestionRuntime / AgentState`。
- 工具层加入 `ToolRegistry`。
- 候选排序后加入 `RecoveryLoop`。
- API 端点说明加入 `agent_state` 和 `recovery`。
- 测试覆盖方向加入 Runtime、ToolRegistry 和 RecoveryLoop。
- 推荐学习顺序加入 `sql_agent/runtime/`。
- 后续计划中将“适配真实模型”修正为“扩展本地模型后端和更多 LLM provider”，避免和现有 OpenAI/Azure adapter 冲突。

### 2. 项目亮点和面试材料

更新内容：

- 项目一句话定位加入 Agent Runtime、Tool Registry 和 Recovery Loop。
- 面试主链路加入状态机阶段。
- 增加“为什么用了状态机但没有直接上 LangGraph”的回答。
- 增加 ToolRegistry 和 RecoveryLoop 的面试解释。
- 简历描述加入 QuestionRuntime / AgentState、ToolRegistry 和 RecoveryLoop。
- API 展示字段加入 `agent_state` 和 `recovery`。

### 3. 学习资料

更新内容：

- `docs/study-plan/README.md`：学习目标加入 Runtime、AgentState 和 RecoveryLoop。
- `docs/study-plan/technical-cheatsheet.md`：主链路、核心数据对象、测试矩阵和 Runtime 组件表更新。
- `docs/study-plan/diagrams.md`：主链路图加入 QuestionRuntime、ToolRegistry、RecoveryLoop，并新增 AgentState 状态机图。
- `docs/study-plan/interview-playbook.md`：五分钟介绍、十五分钟提纲和后续优先级更新。
- `docs/study-plan/14-day-learning-plan.md`：Day 3 加入 Runtime 测试和状态机学习任务，移除不存在的 `.env.example` 引用。

### 4. 历史计划与架构文档

更新内容：

- `ARCHITECTURE.md` 增加说明：该文档是上游 Dataherald 的历史架构调研，当前实现以 README 和 runtime 代码为准。
- `docs/superpowers/plans/` 增加历史计划说明，避免旧计划被误读成当前状态。
- `docs/iterations/2026-08-13-230519-data-agent-2-0-deepening.md` 标明当时 SQL AST 仍是后续方向，当前已经在 2026-08-15 迭代落地。

## 当前项目最新能力快照

当前主链路可以概括为：

```text
FastAPI /api/v1/question
-> QuestionRuntime / AgentState
-> Conversation + DatabaseConnection + SchemaScanner
-> SemanticQueryPlan + semantic SQL
-> ContextStore + Feedback verified query
-> ReAct / Plan-and-Solve Agent
-> ToolRegistry / AgentToolkit
-> DAIL / DIN correction
-> CandidateRanker execution evidence
-> RecoveryLoop
-> ResultAnalyzer grounded answer
-> VisualizationRecommender
-> SQLResponse(answer, sql, result, analysis, visualization, candidates, agent_state, recovery)
```

## 涉及文件

- `sql_agent/runtime/`
- `sql_agent/api/routes.py`
- `sql_agent/agent/tools.py`
- `tests/fakes.py`
- `tests/test_api_e2e.py`
- `tests/test_agent_state.py`
- `tests/test_tool_registry.py`
- `tests/test_recovery_loop.py`
- `README.md`
- `ARCHITECTURE.md`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
- `docs/study-plan/`
- `docs/superpowers/plans/`
- `docs/iterations/`

## 验证记录

最终验证命令：

```bash
python -m black sql_agent tests main.py
python -m ruff check sql_agent tests main.py
pytest tests -q
python -m compileall -q sql_agent tests main.py
git diff --check
```

结果：

```text
black: 99 files left unchanged
ruff: All checks passed
pytest tests -q: 142 passed, 3 skipped, 2 warnings
compileall: passed
git diff --check: passed
```

说明：

- 3 个 skipped 是真实 OpenAI、MongoDB、ChromaDB 集成测试，需要显式外部环境才运行。
- 2 个 warnings 来自 FastAPI TestClient/httpx/starlette 依赖弃用提示和当前工作区 `.pytest_cache` 权限提示，不影响断言。
- `git diff --check` 只提示 Windows 行尾转换 warning，没有尾随空白错误。
