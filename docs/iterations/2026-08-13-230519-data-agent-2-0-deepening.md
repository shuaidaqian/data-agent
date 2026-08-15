# Data Agent 2.0 深化迭代记录

时间：2026-08-13 23:05:19

## 本次目标

本次迭代围绕“让项目从 demo 更像系统”推进六个 2.0 能力：

1. Semantic Layer 2.0：业务语义治理。
2. Evaluation Benchmark 2.0：真正可量化。
3. Feedback 2.0：从“能存反馈”到“能学习”。
4. CandidateRanker 2.0：从评分排序到可解释决策。
5. ResultAnalyzer 2.0：从“可信回答”到“分析洞察”。
6. Visualization 2.0：从 spec 到可消费分析资产。

本次没有引入 `sqlglot`，SQL AST 级治理、复杂策略引擎和生产级权限审计仍保留为后续方向。

## 完成内容

### 1. Semantic Layer 2.0

新增能力：

- 指标治理字段：`version`、`owner`、`certified`。
- 时间维度：维度支持 `type=time`、`grain` 和 `grain_expressions`。
- 时间粒度识别：支持 `day`、`month`、`quarter`、`year`。
- 多指标查询：一个问题可以同时命中多个 metric。
- 简单关系 Join：semantic model 中声明 `relationships` 后，compiler 可以编译一跳 Join。
- 歧义澄清：多个指标共享同一业务词时返回 `NEEDS_CLARIFICATION` 和 `clarification_options`。

效果：

- SQL 不再只是 LLM 的直接输出，而是可以从 `SemanticQueryPlan` 编译得到。
- 指标口径和治理信息可以进入模型层，面试时可以解释为“业务语义治理”而不是裸 schema prompt。

### 2. Feedback 2.0

新增能力：

- 结构化错误原因枚举：
  - `WRONG_TABLE`
  - `WRONG_COLUMN`
  - `WRONG_FILTER`
  - `WRONG_JOIN`
  - `WRONG_AGGREGATION`
  - `WRONG_METRIC_DEFINITION`
  - `UNGROUNDED_ANSWER`
  - `VISUALIZATION_WRONG`
- verified query 生命周期：
  - `PENDING_REVIEW`
  - `VERIFIED`
  - `DEPRECATED`
  - `REJECTED`
- corrected SQL 沉淀为 verified query 时写入 `quality_signals`。
- 对 `WRONG_METRIC_DEFINITION` 反馈生成语义模型更新建议，例如从 corrected SQL 中识别 `WHERE status = 'paid'` 并建议补充 metric default filter。
- 新增 `InMemoryStorageBackend`，方便本地开发和测试。

效果：

- 反馈不再只是记录文本，而是有结构化原因、生命周期和可学习建议。
- 当前仍不自动修改 semantic model，避免 feedback 误伤业务口径。

### 3. CandidateRanker 2.0

新增能力：

- `score_breakdown`：评分拆解字段。
- `selection_reason`：候选选择原因。
- `source` 支持 `verified`、`semantic`、`agent`。
- `result_shape`：结果形状校验。
- 计数问题校验单行单指标。
- 分组问题校验维度列 + 指标列。
- 趋势问题校验时间字段 + 指标列。
- verified query 命中加分。
- semantic plan 匹配加分。
- API 层将 verified SQL 和 semantic plan 传入 ranker，2.0 能力已接入主链路。

效果：

- 系统不再只返回一个分数，而是能解释“为什么选这条 SQL”。
- 对 SQL 执行成功但形状不匹配的问题可以降权，降低“可执行但不回答问题”的风险。

### 4. ResultAnalyzer 2.0

新增能力：

- `FindingType`：
  - `single_metric`
  - `top_k`
  - `comparison`
  - `trend`
  - `distribution`
  - `empty_result`
  - `data_quality_warning`
- 多行结果洞察：
  - Top 1。
  - Top K。
  - max/min。
  - 简单差值。
  - 简单占比。
- why 类问题会在 `limitations` 中说明当前 SQL result 不能证明因果或原因，不会把相关性结果包装成因果解释。
- 每个 key finding 继续保留 `SQL result:` evidence。
- API analysis 中透出 `finding_type`。

效果：

- 最终结果不只是“返回 SQL”或“返回一行摘要”，而是能给出可追溯洞察。
- 对抗式审查下更稳：遇到 why 问题不会强行编造原因。

### 5. Visualization 2.0

新增能力：

- `VisualizationRecommendation` 增加：
  - `echarts_option`
  - `validation`
  - `supports_finding`
- 图表字段校验：
  - x 字段存在。
  - y 字段存在。
  - y 字段为数值。
  - line chart 的 x 字段必须是时间字段。
- 支持图表：
  - `metric_card`
  - `bar`
  - `line`
  - `table`
  - `pie`，仅用于占比、比例、份额场景。
- ECharts option 可直接给前端消费。

效果：

- API 返回从“文本洞察”扩展到“可展示分析资产”。
- 图表推荐有校验结果，不会盲目把不合适的字段塞进图表。

### 6. Evaluation Benchmark 2.0

新增能力：

- `EvaluationCase` 增加 `tags` 和 `expected_visualization_type`。
- `EvaluationReport` 增加：
  - `tag_metrics`
  - `error_breakdown`
- 错误归因：
  - `SEMANTIC_MISS`
  - `SQL_INVALID`
  - `EXECUTION_MISMATCH`
  - `UNGROUNDED_ANSWER`
  - `MISSING_EVIDENCE`
  - `WRONG_VISUALIZATION`
- 新增 `sql_agent/eval/run_api_cases.py`：
  - `DemoSQLiteBuilder` 构造 demo SQLite。
  - `ApiCaseRunner` 批量调用 `/api/v1/question`。
  - `write_markdown_report()` 输出带时间戳的 Markdown 报告到 `docs/eval-reports/`。

效果：

- 评估从单一总分扩展到按能力域分析。
- 失败不只是 failed，而是能归因到 SQL、执行、语义、grounding 或可视化。

## 文档更新

已更新：

- `README.md`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
- `docs/superpowers/plans/2026-08-13-data-agent-2-0-deepening.md`

文档中的项目描述已从 Semantic Layer / Feedback / Evaluation 1.0 更新到 2.0 能力；后续已删除外部服务测试。

## 测试结果

定向新增 2.0 测试：

```text
pytest tests\test_semantic_layer_2.py tests\test_feedback_2.py tests\test_candidate_ranking_2.py tests\test_result_analysis_2.py tests\test_visualization_2.py tests\test_eval_benchmark_2.py -q
15 passed, 1 warning
```

全量模块测试：

```text
pytest tests -q
历史模块测试已通过；后续已删除外部服务测试。
```

已验证 API 端到端：

```text
pytest tests\test_api_e2e.py -q
4 passed, 2 warnings
```

## 效果分析

本次迭代后，项目亮点可以更清晰地归纳为六个闭环：

1. Semantic Layer 解决业务口径。
2. Verified Query 解决持续学习。
3. CandidateRanker 解决 LLM 不可靠。
4. ResultAnalyzer 解决答案可信和洞察表达。
5. Evaluation Benchmark 解决质量度量。
6. Visualization Spec / ECharts 解决结果可消费。

相比上一版，本次最大的变化不是“多了几个字段”，而是把系统的解释能力和复盘能力补齐了：

- semantic plan 可解释查询逻辑。
- candidate score breakdown 可解释 SQL 选择。
- finding evidence 可解释答案来源。
- visualization validation 可解释图表可用性。
- error breakdown 可解释评估失败原因。
- feedback suggestion 可解释系统如何从错误中学习。

## 当前边界

1. 没有 SQL AST 级解析，alias、CTE、子查询列级权限仍是后续方向。
2. Semantic planner 仍是启发式，不是 LLM semantic parser。
3. Join 编译仅支持 semantic model 中声明的一跳关系。
4. verified query 生命周期没有人工审核 UI。
5. semantic update suggestion 只产出建议，不会自动修改模型文件。
6. ECharts option 是服务端生成的可消费资产，但没有前端页面承载。
7. 后续清理迭代已删除外部服务测试，测试重点收敛到 SQLite + MockLLM 原型链路。

## 面试表达建议

可以这样概括本次 2.0 后的项目：

> 我做的不是简单 Text-to-SQL，而是一个轻量 Data Agent 闭环。系统先用 Semantic Layer 管理业务指标口径，把问题解析成 SemanticQueryPlan；再综合 semantic SQL、verified query 和 Agent SQL 形成候选集；CandidateRanker 对候选做 schema 校验、真实执行、结果形状校验和可解释排序；ResultAnalyzer 只基于 SQL result 生成 grounded 洞察；VisualizationRecommender 输出可消费 ECharts option；Feedback 和 Evaluation Benchmark 则让系统可以持续学习和量化回归。

最值得给面试官展示的字段：

- `semantic_plan`
- `candidates[].score_breakdown`
- `candidates[].selection_reason`
- `candidates[].result_shape`
- `analysis.key_findings[].finding_type`
- `analysis.key_findings[].evidence`
- `visualization.echarts_option`
- `visualization.validation`
- evaluation report 的 `tag_metrics` 和 `error_breakdown`

## 后续建议

下一阶段最有价值的方向：

1. 引入 SQL AST parser，做 alias、CTE、子查询和列级权限校验。
2. 做 semantic model 管理 API 和审核流。
3. verified query 召回接 VectorBackend，从 token overlap 升级到语义召回。
4. 增加前端结果页，展示 answer、SQL、evidence、candidate decision 和 ECharts 图表。
5. 接入 Agent trace，记录 semantic plan、工具调用、候选集、排序证据和结果分析。
