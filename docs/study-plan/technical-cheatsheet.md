# SQL Agent 技术细节速查表

## 1. 项目一句话

这是一个基于 Dataherald 架构分析后重构的轻量级 Data Agent / NL->SQL 原型，重点验证 Semantic Layer 业务语义治理、原生 ReAct、Plan-and-Solve、多轮上下文、Schema Linking、执行反馈自纠错、多候选 SQL 可解释排序、grounded 结果洞察、可消费 ECharts 可视化资产和反馈评估闭环。

## 2. 技术栈

| 技术 | 项目中用途 | 面试回答重点 |
|------|------------|--------------|
| FastAPI | 提供 REST API，入口是 `main.py` 和 `sql_agent/api/routes.py` | 高性能 Python API 框架，Pydantic 请求响应模型，自动 Swagger |
| Pydantic | 定义 API 请求和响应模型 | 让 HTTP 输入输出有结构和校验 |
| dataclass | 定义内部核心数据对象 | 适合轻量数据容器，比 dict 更清晰 |
| SQLAlchemy | 数据库连接、执行 SQL、inspect schema | 屏蔽不同数据库差异，支持 engine 和 inspector |
| OpenAI SDK | LLM 生成、embedding | 通过 `LLMBackend` 抽象，避免业务层直接依赖 SDK |
| ChromaDB | Golden SQL 向量检索 | 根据用户问题召回相似 few-shot 示例 |
| MongoDB | 文档存储 | 保存连接、Golden SQL、表描述、指令等结构化记录 |
| pytest | 单元测试、集成测试、端到端测试 | fake 组件隔离外部依赖，真实集成测试按环境跳过 |
| sqlparse / sql_metadata | SQL 解析和表名识别 | 工具白名单和 SQL 安全校验的辅助能力 |

## 3. 主链路

```text
POST /api/v1/question
  -> QuestionRequest
  -> create_system()
  -> StorageBackend / VectorBackend / LLMBackend
  -> load DatabaseConnection
  -> SQLDatabase
  -> SchemaScanner.scan_all_tables()
  -> SemanticPlanner 生成 SemanticQueryPlan
  -> SemanticSQLCompiler 编译 semantic SQL 候选
  -> ContextRetriever.retrieve_all_context()
  -> FeedbackService 召回 verified query
  -> ConversationManager.get_or_create()
  -> AgentSelector.generate_sql()
  -> ReActAgent 或 PlanSolveAgent
  -> AgentToolkit 工具调用
  -> DAILStyleCorrector.correct()
  -> CandidateRanker 执行验证、形状校验、评分拆解
  -> ResultAnalyzer 生成 answer / summary / key_findings
  -> VisualizationRecommender 生成 spec / ECharts option
  -> SQLResponse
```

## 4. 核心数据对象

| 类 | 职责 | 面试关键词 |
|----|------|------------|
| `DatabaseConnection` | 数据库连接配置 | alias、connection_uri、schemas、metadata |
| `ColumnMetadata` | 列级元数据 | 类型、描述、主键、外键、样本值、低基数 |
| `TableDescription` | 表结构描述 | DDL、列信息、行数、扫描状态 |
| `Prompt` | 单轮用户问题 | text、db_connection_id、schemas |
| `Conversation` | 多轮会话 | turns、created_at、updated_at |
| `ConversationTurn` | 一轮对话 | role、content、sql、sql_result |
| `SQLGeneration` | SQL 生成结果 | sql、status、confidence、intermediate_steps、correction |
| `GoldenSQL` | few-shot 示例 | prompt_text、sql、tables_used、complexity |
| `Instruction` | 管理员规则 | 约束 SQL 风格和业务规则 |
| `AgentConfig` | Agent 配置 | mode、max_iterations、self_correction |
| `SemanticQueryPlan` | 语义查询中间表示 | metrics、dimensions、filters、time_grain、clarification_options |
| `SQLCandidate` | 候选 SQL 决策对象 | score_breakdown、selection_reason、source、result_shape、execution |
| `AnalysisResult` | 结果分析输出 | answer、summary、key_findings、limitations、visualization |

## 5. Agent 三件套

### SQLAgent

统一抽象接口：

- `generate_sql()`：生成 SQL。
- `stream_sql()`：流式生成。
- `estimate_complexity()`：估计问题复杂度。
- `extract_sql_from_output()`：从 LLM 输出中提取 SQL 代码块。

### ReActAgent

适合简单和中等复杂度问题。

```text
Thought -> Action -> Observation -> Thought -> ... -> Final SQL
```

优点：

- 控制流清晰。
- 工具调用可观测。
- 方便记录中间步骤。

风险：

- 依赖 LLM 按格式输出。
- 复杂查询可能陷入多轮工具调用。

### PlanSolveAgent

适合复杂 SQL。

```text
Plan Phase -> Execute Phase -> Final SQL
```

适用：

- 多表 JOIN。
- 聚合排序。
- ranking。
- time series。
- CTE / window function。

## 6. AgentToolkit 工具

| 工具 | 输入 | 输出 | 作用 |
|------|------|------|------|
| `SqlDbQuery` | SQL | 查询结果或错误 | 执行验证 SQL |
| `SystemTime` | 空 | 当前时间 | 处理时间类问题 |
| `DbTablesWithRelevanceScores` | 用户问题 | 相关表和分数 | embedding 找表 |
| `DbRelevantTablesSchema` | 表名列表 | DDL/schema | 获取表结构 |
| `DbColumnEntityChecker` | 表列和实体 | 相似值 | 检查实体值是否存在 |
| `DbRelevantColumnsInfo` | 表列列表 | 列描述和样本 | 给 LLM 补列级上下文 |
| `FewshotExamplesRetriever` | 样本数量 | 问题-SQL 示例 | few-shot 引导 |
| `GetAdminInstructions` | 空 | 管理员规则 | 注入业务约束 |

## 7. Schema Linking

核心思想：把数据库外键关系建成图，再为多表查询提供 JOIN 路径。

```text
sales.employee_id -> employees.id
employees.department_id -> departments.id
sales.product_id -> products.id
```

能解决：

- LLM 不知道表之间如何 JOIN。
- 多表查询缺少 ON 条件。
- 表名、列名和自然语言实体之间需要对齐。

局限：

- 依赖数据库外键质量。
- 外键缺失时只能退化为启发式匹配。
- 复杂业务关系可能不在 schema 中。

## 8. 自纠错

### DIN-SQL 风格

```text
验证 SQL 是否回答问题 -> 定位错误 -> 生成修正版 -> 验证
```

关注语义正确性。

### DAIL-SQL 风格

```text
执行 SQL -> 获取数据库反馈 -> LLM 修正 -> 再执行
```

关注执行反馈。

关键面试点：

- SQL 可执行不代表语义正确。
- 返回 0 行可能是条件错，也可能是数据本来为空。
- 自纠错需要限制轮数，避免无限循环和成本失控。

## 9. 测试体系

| 测试类型 | 文件 | 作用 |
|----------|------|------|
| 数据模型测试 | `tests/test_core_types.py` | 保证核心对象字段和默认值正确 |
| SQL 执行测试 | `tests/test_sql_database.py` | 验证查询、JOIN、注入拦截 |
| 集成查询测试 | `tests/test_integration.py` | 验证聚合、子查询、三表 JOIN |
| Schema 测试 | `tests/test_schema_linking.py`、`tests/test_schema_scanner_samples.py` | 验证 schema 理解能力 |
| Agent 工具测试 | `tests/test_agent_tools.py` | 验证工具输入输出和白名单 |
| API E2E 测试 | `tests/test_api_e2e.py` | 用 fake 组件测试完整 API 链路 |
| Semantic 2.0 测试 | `tests/test_semantic_layer_2.py` | 验证指标治理、多指标、时间粒度、Join 和歧义澄清 |
| Ranking 2.0 测试 | `tests/test_candidate_ranking_2.py` | 验证来源识别、评分拆解、选择理由和结果形状 |
| Analysis 2.0 测试 | `tests/test_result_analysis_2.py` | 验证 Top K、占比、why 限制和 finding type |
| Visualization 2.0 测试 | `tests/test_visualization_2.py` | 验证 ECharts option、字段校验和 pie |
| Evaluation 2.0 测试 | `tests/test_eval_benchmark_2.py` | 验证 tag metrics、错误归因和 API case runner |
| 真实集成测试 | `tests/test_real_integrations.py` | 有环境变量时测试真实 OpenAI/Mongo/Chroma |

当前基线：

```text
pytest -q tests
119 passed, 3 skipped, 2 warnings
```

## 10. Semantic Layer 2.0

核心思想：业务口径必须显式治理，不能让 LLM 从裸 schema 里猜。

当前能力：

- 指标治理：`version`、`owner`、`certified`。
- 指标和维度同义词。
- 默认过滤条件。
- 时间维度和粒度：`day`、`month`、`quarter`、`year`。
- 多指标查询。
- 一跳 relationship Join 编译。
- 歧义澄清：返回 `NEEDS_CLARIFICATION` 和候选指标。

面试关键词：

> SQL 是 SemanticQueryPlan 的编译产物，不是模型自由发挥的字符串。

## 11. CandidateRanker 2.0

核心思想：不相信第一条 SQL，真实执行后再排序。

当前能力：

- `source`：`semantic`、`verified`、`agent`。
- `score_breakdown`：评分拆解。
- `selection_reason`：选择理由。
- `result_shape`：结果形状校验。
- verified query bonus。
- semantic plan match bonus。
- count / group-by / trend 问题的形状校验。

面试关键词：

> 可执行不等于正确，结果形状也要符合问题意图。

## 12. ResultAnalyzer 2.0

核心思想：业务用户要答案和洞察，不只是 SQL。

当前能力：

- `FindingType`：single_metric、top_k、comparison、trend、distribution、empty_result、data_quality_warning。
- Top 1 / Top K。
- max / min / 差值。
- 简单占比。
- why 类问题返回 limitation，不把相关性包装成因果。
- 每个关键发现必须绑定 `SQL result:` evidence。

面试关键词：

> 系统执行 SQL，LLM 只分析受控结果；不 grounded 就回退。

## 13. Visualization 2.0

核心思想：把结果从文本答案扩展成可消费分析资产。

当前能力：

- `metric_card`
- `bar`
- `line`
- `table`
- `pie`，仅用于占比和份额场景。
- ECharts option。
- 字段校验：x/y 存在、y 数值、line 的 x 是时间字段。
- `supports_finding` 绑定文字洞察和图表。

## 14. Feedback + Evaluation 2.0

Feedback：

- wrong reason enum。
- verified query 生命周期。
- quality signals。
- semantic model update suggestion。

Evaluation：

- valid rate。
- execution accuracy。
- answer grounding rate。
- semantic plan accuracy。
- verified query hit rate。
- tag metrics。
- error breakdown。
- API case runner 和 Markdown report。

## 15. 项目风险和改进方向

| 风险 | 说明 | 改进 |
|------|------|------|
| LLM 幻觉 | 生成不存在的表或列 | schema 白名单、执行验证、few-shot |
| Schema 太大 | prompt 放不下 | schema 分层检索、表级召回、列级压缩 |
| 外键缺失 | JOIN 路径找不到 | 业务关系配置、历史 SQL 学习 |
| SQL 安全 | LLM 可能生成危险 SQL | 只读账号、白名单、AST 解析、审计日志 |
| 执行反馈误导 | 0 行不一定错误 | 结合语义检查和样本统计 |
| 真实服务不稳定 | OpenAI/Mongo/Chroma 依赖环境 | fake 测试 + 真实集成测试分层 |
| 语义模型误维护 | 指标口径如果配置错，SQL 会稳定地错 | owner/certified、审核流、benchmark 回归 |
| 候选排序误判 | 真实执行成功但语义仍可能错 | golden benchmark、verified query、LLM evaluator、人工反馈 |
| 结果分析过度解释 | 相关性结果被说成因果 | finding type、why limitation、grounding 校验 |
| 可视化误导 | 字段类型不适合图表 | chart validation、前端展示限制 |
