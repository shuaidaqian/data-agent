# 2026-08-13 00:05:02 Semantic Layer / Feedback / Evaluation / Visualization 迭代记录

> 历史记录说明：本文记录的是 Semantic Layer / Feedback / Evaluation / Visualization 1.0 当次迭代状态，测试数量和边界说明保留当时事实。当前项目已经在 2026-08-13 晚间迭代升级到 Data Agent 2.0，详见 `docs/iterations/2026-08-13-230519-data-agent-2-0-deepening.md`。

## 本轮目标

本轮目标是把项目从“可执行的 NL-to-SQL Agent 原型”继续升级为“基于语义层、执行证据、反馈学习和评估闭环的企业数据问答 Agent 原型”。

最终项目叙事收敛为五个亮点：

1. **Semantic Layer 驱动的 NL-to-SQL**：指标、维度、同义词、默认过滤条件，不再只依赖裸 schema prompt。
2. **SemanticQueryPlan 中间表示**：查询逻辑可解释、可校验，SQL 只是编译产物。
3. **Candidate Ranking + Execution Evidence**：不相信第一条 SQL，统一执行、评分和排序。
4. **Grounded Result Analysis**：用户拿到的是答案，不只是 SQL，答案绑定 SQL result evidence。
5. **Feedback + Evaluation Loop**：错误能沉淀成 verified query，并用 benchmark 衡量 valid rate、execution accuracy、grounding rate。

## 实现内容

### 1. Semantic Layer

新增 `sql_agent/semantic/`：

- `types.py`：定义 `MetricDefinition`、`DimensionDefinition`、`SemanticModel`、`SemanticQueryPlan`。
- `registry.py`：从 YAML 加载语义模型，并根据问题匹配指标和维度。
- `planner.py`：用稳定启发式把自然语言问题解析成语义计划。
- `validator.py`：校验计划中的指标和维度必须来自语义模型白名单。
- `compiler.py`：把语义计划编译成 SQL。

新增示例语义模型：

- `examples/semantic_model.yml`

第一版支持指标名称、label、同义词匹配，维度名称、label、同义词匹配，指标默认过滤条件，Top-K 意图识别和分组聚合 SQL 编译。

### 2. API 语义计划接入

`/api/v1/question` 新增：

- `semantic_plan`
- `visualization`

当配置 `SEMANTIC_MODEL_PATH` 时，API 会加载语义模型、生成 `SemanticQueryPlan`、校验计划、编译语义 SQL，并将语义 SQL 与 Agent SQL、verified query SQL 合并为候选，统一交给 `CandidateRanker` 执行验证和排序。

### 3. Feedback + Verified Query

新增 `sql_agent/feedback/`：

- `types.py`：定义 `QueryFeedback`、`VerifiedQuery`、`VerifiedQueryMatch`。
- `service.py`：保存反馈、将 corrected SQL 沉淀成 verified query、按问题相似度召回可信 SQL。

新增 API：

- `POST /api/v1/feedback`
- `GET /api/v1/feedback`
- `GET /api/v1/verified-queries`

当用户反馈中包含 `corrected_sql` 时，系统会自动创建 verified query。后续相似问题会先召回 verified query，并把它加入候选 SQL 列表。

### 4. Visualization Spec

新增 `sql_agent/visualization/`：

- `types.py`：定义 `VisualizationRecommendation`。
- `recommender.py`：基于 SQL result 的结果形状生成确定性图表建议。

当前规则：

- 单行单列：`metric_card`
- 时间字段 + 数值字段：`line`
- 分类字段 + 数值字段：`bar`
- 其他明细：`table`

### 5. Evaluation Harness

新增：

- `sql_agent/eval/harness.py`
- `eval_cases/demo_semantic.yml`

评估指标：

- `valid_rate`
- `execution_accuracy`
- `answer_grounding_rate`
- `semantic_plan_accuracy`
- `verified_query_hit_rate`

第一版是离线评估框架，输入标准响应 dict 后计算指标，并可生成 Markdown 报告。后续可以接真实 API 批量请求。

## 测试覆盖

新增测试：

- `tests/test_semantic_layer.py`
- `tests/test_feedback.py`
- `tests/test_visualization.py`
- `tests/test_eval_harness.py`

更新测试：

- `tests/test_api_e2e.py`
- `tests/test_result_analysis.py`

本轮关键验证：

```text
pytest tests/test_semantic_layer.py tests/test_feedback.py tests/test_visualization.py tests/test_eval_harness.py tests/test_api_e2e.py tests/test_result_analysis.py -q
22 passed, 2 warnings

pytest tests -q
历史模块测试已通过；后续已删除外部服务测试。

python -m compileall -q sql_agent tests main.py
exit 0
```

## 实现效果

本轮后，请求链路升级为：

```text
用户问题
-> SemanticModelRegistry 加载业务语义模型
-> SemanticPlanner 生成 SemanticQueryPlan
-> SemanticPlanValidator 校验指标和维度
-> SemanticSQLCompiler 编译语义 SQL
-> VerifiedQueryRetriever 召回可信历史 SQL
-> Agent 生成补充 SQL
-> CandidateRanker 统一执行验证和排序
-> ResultAnalyzer 生成 grounded answer
-> VisualizationRecommender 生成图表建议
-> API 返回 answer + semantic_plan + sql + result + analysis + visualization + candidates
```

这让项目从“LLM 生成 SQL”进一步升级为“业务语义约束、执行证据决策、反馈学习和质量评估”的 Data Agent 原型。

## 风险与边界

1. Semantic planner 当前是启发式匹配，不是复杂 LLM semantic parser。
2. SQL compiler 当前支持单指标、简单维度、默认过滤、Top-K，不支持复杂多指标组合和跨表 join 编译。
3. Verified query 召回使用轻量 token overlap，不是向量检索。
4. Evaluation Harness 当前是离线响应评估，尚未直接驱动 FastAPI 批量请求。
5. Visualization Spec 是规则推荐，不做真正图表渲染。

这些边界是有意保留的：第一版目标是让项目具备可讲清楚的企业 Data Agent 架构，而不是一次性复制完整商业 BI 平台。

## 面试表达

可以这样讲：

> 我后来发现 NL-to-SQL 的核心难点不是 SQL 语法，而是业务语义和可信度。所以我加了一层轻量 Semantic Layer，把指标、维度、同义词和默认过滤条件显式建模。用户问题先解析成 SemanticQueryPlan，经校验后编译为 SQL，SQL 再和 Agent 输出、verified query 一起进入候选排序。最终答案必须绑定 SQL result evidence，用户反馈还能沉淀成 verified query，评估脚本会统计 valid rate、execution accuracy 和 answer grounding rate。
