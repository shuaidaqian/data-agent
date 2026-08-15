# Semantic Data Agent Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 NL-to-SQL Agent 升级为具备轻量 Semantic Layer、反馈学习、评估闭环和可视化推荐的数据问答 Agent 原型。

> 计划状态说明：该计划对应 Semantic Layer / Feedback / Evaluation / Visualization 1.0 迭代，已完成并在后续升级到 Data Agent 2.0、SQL AST safety、business benchmark、QuestionRuntime / AgentState、ToolRegistry 和 RecoveryLoop。当前最新实现以 `README.md`、`docs/project-highlights.md` 和最新 `docs/iterations/` 记录为准。

**Architecture:** 新增 `semantic/`、`feedback/`、`visualization/` 三个聚焦模块，并扩展 `eval/` 与 `/api/v1/question`。请求链路先尝试基于语义模型生成 `SemanticQueryPlan` 和语义 SQL 候选，再合并 Agent 候选与 verified query 候选，最后统一走 CandidateRanker、ResultAnalyzer 和 VisualizationRecommender。

**Tech Stack:** Python dataclasses、PyYAML、FastAPI、SQLAlchemy、pytest、现有 MemoryStorage/MockLLM 测试体系。

---

## File Structure

- Create `sql_agent/semantic/types.py`: 语义模型、指标、维度、过滤条件、语义计划数据结构。
- Create `sql_agent/semantic/registry.py`: YAML 加载、存储同步、指标/维度匹配。
- Create `sql_agent/semantic/planner.py`: 从自然语言问题生成 `SemanticQueryPlan`。
- Create `sql_agent/semantic/compiler.py`: 将语义计划编译为 SQL。
- Create `sql_agent/semantic/validator.py`: 校验语义计划引用的指标、维度和过滤字段。
- Create `sql_agent/semantic/__init__.py`: 导出公共接口。
- Create `sql_agent/feedback/types.py`: 查询反馈和 verified query 数据结构。
- Create `sql_agent/feedback/service.py`: 反馈保存、修正 SQL 沉淀、verified query 召回。
- Create `sql_agent/feedback/__init__.py`: 导出公共接口。
- Create `sql_agent/visualization/recommender.py`: 基于 SQL result 生成 chart recommendation 和 spec。
- Create `sql_agent/visualization/types.py`: 可视化推荐数据结构。
- Create `sql_agent/visualization/__init__.py`: 导出公共接口。
- Modify `sql_agent/analysis/types.py`: `AnalysisResult` 增加可选 `visualization`。
- Modify `sql_agent/analysis/result_analyzer.py`: 调用可视化推荐器。
- Modify `sql_agent/api/routes.py`: 返回 `semantic_plan`、`visualization`，新增反馈 API。
- Modify `sql_agent/core/config.py`: 增加 `SEMANTIC_MODEL_PATH`。
- Modify `sql_agent/eval/harness.py`: 新增评估脚本入口。
- Create `examples/semantic_model.yml`: demo 语义模型。
- Create `eval_cases/demo_semantic.yml`: demo 评估用例。
- Add tests:
  - `tests/test_semantic_layer.py`
  - `tests/test_feedback.py`
  - `tests/test_visualization.py`
  - `tests/test_eval_harness.py`
  - extend `tests/test_api_e2e.py`

## Task 1: Semantic Layer

- [ ] 写 `tests/test_semantic_layer.py`，覆盖 YAML 加载、metric/dimension 匹配、默认过滤条件、SQL 编译。
- [ ] 运行 `pytest tests/test_semantic_layer.py -q`，确认因 `sql_agent.semantic` 不存在而失败。
- [ ] 实现 `semantic/types.py`、`registry.py`、`planner.py`、`compiler.py`、`validator.py`。
- [ ] 添加 `examples/semantic_model.yml`。
- [ ] 运行 `pytest tests/test_semantic_layer.py -q`，确认通过。

## Task 2: Feedback + Verified Query

- [ ] 写 `tests/test_feedback.py`，覆盖反馈保存、corrected SQL 转 verified query、问题相似召回。
- [ ] 运行 `pytest tests/test_feedback.py -q`，确认因 `sql_agent.feedback` 不存在而失败。
- [ ] 实现 `feedback/types.py`、`feedback/service.py`。
- [ ] 在 `api/routes.py` 新增 `POST /feedback`、`GET /feedback`、`GET /verified-queries`。
- [ ] 运行 `pytest tests/test_feedback.py -q`，确认通过。

## Task 3: Visualization Spec

- [ ] 写 `tests/test_visualization.py`，覆盖 metric card、bar、line、table 推荐。
- [ ] 运行 `pytest tests/test_visualization.py -q`，确认因 `sql_agent.visualization` 不存在而失败。
- [ ] 实现 `visualization/types.py`、`visualization/recommender.py`。
- [ ] 扩展 `AnalysisResult` 和 `ResultAnalyzer`，把 `visualization` 纳入分析结果。
- [ ] 运行 `pytest tests/test_visualization.py tests/test_result_analysis.py -q`，确认通过。

## Task 4: API Integration

- [ ] 扩展 `tests/test_api_e2e.py`，断言 `/question` 返回 `semantic_plan` 和 `visualization`。
- [ ] 运行 API 测试，确认失败。
- [ ] 修改 `api/routes.py`，在 Agent 前加载语义模型、生成语义计划和语义 SQL 候选。
- [ ] 合并语义 SQL、verified query SQL 和 Agent SQL，再交给 CandidateRanker。
- [ ] 返回 `semantic_plan`、`visualization`。
- [ ] 运行 `pytest tests/test_api_e2e.py -q`，确认通过。

## Task 5: Evaluation Harness

- [ ] 写 `tests/test_eval_harness.py`，覆盖 demo case 评估和 markdown 报告生成。
- [ ] 运行测试，确认失败。
- [ ] 实现 `sql_agent/eval/harness.py` 和 `eval_cases/demo_semantic.yml`。
- [ ] 运行 `pytest tests/test_eval_harness.py -q`，确认通过。

## Task 6: Docs and Iteration Record

- [ ] 新增迭代记录 `docs/iterations/<timestamp>-semantic-layer-feedback-eval-visualization.md`。
- [ ] 更新 README、project highlights、interview prep。
- [ ] 运行 `pytest tests -q`、`python -m compileall -q sql_agent tests main.py`、`python -m ruff check sql_agent tests main.py`。
- [ ] 检查 diff，清理无用代码。
