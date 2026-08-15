# SQL Agent 项目亮点梳理

## 一句话定位

这是一个参考 Dataherald 架构并结合 Data Agent 思路重构的轻量级企业数据问答 Agent 系统。它不是简单让 LLM 一次性生成 SQL，而是把 AgentState 状态机、Tool Registry、Recovery Loop、Semantic Layer 2.0、SemanticQueryPlan、数据库环境感知、工具调用、Schema Linking、多轮记忆、执行反馈自纠错、SQL AST 安全校验、候选 SQL 可解释排序、grounded 结果洞察、ECharts 可视化资产、反馈学习和可复现业务 Benchmark 串成一个可测试的工程闭环。

## 面试官容易眼前一亮的亮点

### 1. 原生 ReAct + Plan-and-Solve 双 Agent 路由

项目没有直接依赖 LangChain Agent 黑盒，而是自己实现了 ReAct 的 Thought-Action-Observation 循环，并额外实现 Plan-and-Solve Agent 处理复杂 SQL。

可讲的技术点：

- 简单问题走 ReAct，减少规划成本。
- 复杂问题走 Plan-and-Solve，先分析表、JOIN、过滤、聚合和排序。
- `AgentSelector` 根据问题复杂度自动选择执行路径。
- 每一步工具调用都有中间步骤记录，方便调试和解释。
- `/api/v1/question` 由 `QuestionRuntime` 编排，一次问答会经过 `LOAD_CONTEXT`、`PLAN_QUERY`、`GENERATE_SQL`、`RANK_CANDIDATES`、`RECOVER`、`ANALYZE_RESULT`、`FINALIZE` 等状态。
- API 返回 `agent_state` 和 `recovery` 摘要，能说明当前请求是否完成、是否发生恢复以及恢复次数。

面试表达：

> 我没有把 Text-to-SQL 简单封成一次 LLM 调用，而是实现了一个可控 Agent Runtime。一次请求会进入 AgentState 状态机，先加载上下文和 schema，再做语义计划、SQL 生成、候选执行排序、失败恢复和 grounded 分析。LLM 必须通过受控工具观察数据库，再基于 observation 继续推理，复杂问题则先规划再执行。

### 2. Schema 优先的数据环境感知

项目用 `SchemaScanner` 扫描数据库，而不是只把表名塞给模型。

当前能力：

- 表和视图扫描。
- 列名、类型、主键、外键识别。
- 行数统计。
- distinct/null 统计。
- 样本值采集。
- 低基数字段识别。
- 列级语义标签和同义词生成。

面试表达：

> NL-to-SQL 的核心不是 prompt，而是让 Agent 先理解数据环境。我把 schema 扫描结果结构化为 TableDescription 和 ColumnMetadata，并进一步补充样本值、低基数枚举、语义类型和同义词，帮助 Agent 降低幻觉。

### 3. Schema Linking 和 JOIN 路径发现

项目不只依赖模型猜 JOIN，而是基于外键关系构建 schema graph。

当前能力：

- 根据外键构建关系图。
- 查询多表之间的 JOIN 路径。
- 将自然语言实体和表/列做简单匹配。
- 为复杂多表查询提供结构化 JOIN 建议。

面试表达：

> 对多表查询，我没有完全让 LLM 猜 JOIN 条件，而是从数据库外键构建关系图，通过 Schema Linking 给出可解释的 JOIN 路径。

### 4. SQL AST 安全边界和白名单校验

项目的 LLM 不直接访问数据库，而是通过 `AgentToolkit` 的受控工具访问。

当前能力：

- 基于 `sqlglot` AST 解析 SQL，而不是依赖字符串切分。
- 拦截非 SELECT、多语句、未知表、未知列、歧义未限定列和危险函数。
- 支持 alias、JOIN、CTE 和子查询作用域，避免复杂查询被简单 regex 误判。
- `AgentToolkit.SqlDbQuery` 执行前强制校验。
- 工具通过 `ToolRegistry` 声明式注册，保留工具分类、权限范围、安全要求、超时和参数说明。
- `CandidateRanker` 对每条候选 SQL 附加 `safety` 报告，面试时可以展示为什么某条 SQL 被拒绝。
- SQLite 的 `main/temp` 默认 schema 会规范化为裸表名，业务 benchmark 和工具层口径一致。

面试表达：

> 我把 SQL 安全从 regex 提升到 AST 层。所有候选 SQL 在执行前都会被解析成语法树，只允许访问扫描过的表和列，并且能正确处理 alias、CTE 和子查询作用域。这样模型即使生成危险 SQL、幻觉表名或引用不存在的列，也会在工具层和候选排序层被拦截，并留下结构化 safety evidence。

### 5. 多轮对话不是 prompt 拼接，而是结构化会话对象

项目把单轮 Prompt 扩展成 `Conversation` 和 `ConversationTurn`。

当前能力：

- 保存用户问题、助手 SQL、SQL 执行结果。
- 控制上下文窗口。
- 支持跨请求会话恢复。
- API 使用存储化 `ConversationManager`。

面试表达：

> 我没有把多轮对话做成简单字符串拼接，而是设计了 Conversation 数据模型，保存历史问题、历史 SQL 和执行结果，后续问题可以基于结构化历史做引用消歧。

### 6. 执行反馈自纠错闭环

项目实现了 DIN-SQL 风格和 DAIL-SQL 风格修正器。

当前能力：

- DIN 风格：verify-then-fix，先判断 SQL 是否回答问题，再定位错误。
- DAIL 风格：execute-feedback-fix，执行 SQL 后根据数据库报错或样本结果修正。
- 支持多轮修正，避免一次生成失败就直接返回。

面试表达：

> 我认为 NL-to-SQL 不能只依赖一次生成，所以实现了执行反馈闭环。SQL 生成后会真实执行，根据错误信息或结果反馈再让模型修正。

### 7. Semantic Layer + SemanticQueryPlan

这是当前最能拉开项目层次的新增亮点。

当前能力：

- 通过 YAML 语义模型定义指标、维度、同义词和默认过滤条件。
- 用户问题先命中指标和维度，再生成 `SemanticQueryPlan`。
- 语义计划经过白名单校验后编译为 SQL。
- SQL 不再只是 LLM 直接输出，而是可解释、可校验计划的编译产物。
- Semantic Layer 2.0 进一步补齐指标版本、owner、certified 状态、时间维度、时间粒度、多指标计划、简单关系 Join 和歧义澄清。

面试表达：

> 我后来发现 NL-to-SQL 的核心难点不是 SQL 语法，而是业务语义和指标口径。所以我加了一层轻量 Semantic Layer，把“员工数量”这类业务指标、同义词、维度、时间粒度、默认过滤条件和认证状态显式建模。用户问题会先解析成 SemanticQueryPlan，再编译为 SQL；多指标和歧义场景也能结构化表达，这样查询逻辑可以被审查，而不是完全依赖 LLM 猜。

### 8. 多候选 SQL 可解释排序

这是结果可靠性链路里的关键增强，和 Semantic Layer、verified query 一起构成候选决策层。

当前能力：

- 从 Agent 主输出和中间步骤中收集候选 SQL。
- 候选 SQL 去重。
- 候选 SQL schema 白名单校验。
- 候选 SQL 执行验证。
- 收集 row count、columns、preview、error。
- 综合 schema、执行结果、问题意图和 Evaluator 分数排序。
- 输出 `score_breakdown`、`selection_reason`、`source` 和 `result_shape`，让候选选择可以被复盘。
- verified query 命中和 semantic plan 匹配会进入评分，但仍必须通过真实执行。
- 每条候选 SQL 都带 `safety` 报告，包含 allowed、risk_level、引用表、引用列和违规原因。
- API 返回 `candidates`，让系统选择过程透明可解释。
- 向 API 透出最优候选 SQL 的执行结果，作为最终答案的证据来源。

面试表达：

> 系统不会盲信第一条 SQL，而是对候选 SQL 做执行验证、结果形状校验和可解释排序。最终返回的不只是 SQL，还有候选分数、评分拆解、执行行数、结果列和选择依据，后续自然语言答案也只基于这份受控执行结果生成。

`RecoveryLoop` 会在排序第一的候选不可用时，从后续候选中选择下一个真实执行成功的 SQL；如果全部失败，则返回结构化失败原因，而不是直接把错误 SQL 当答案返回。这让 Agent 具备最基础的“观察失败 -> 选择替代动作”的恢复能力。

### 9. Grounded 结果分析，不止返回 SQL

这是把项目从“SQL 生成器”推进到“数据问答 Agent”的关键增强。

当前能力：

- `/api/v1/question` 透出最优候选 SQL 的真实执行结果，包括 `columns`、`rows`、`row_count` 和 `truncated`。
- 默认启用 `HeuristicResultAnalyzer`，从 SQL result 生成稳定的 `answer`、`summary`、`key_findings`、`limitations` 和 `followup_questions`。
- 可选启用 `LLMResultAnalyzer`，让自然语言回答更流畅，但 LLM 只接收受控 SQL result，不接收数据库连接，也不执行 SQL。
- 每个关键发现必须包含 `SQL result:` evidence。
- 如果 LLM 输出无法解析、缺少 evidence，或回答、摘要、结论中包含 SQL result 中不存在的数值，系统会自动回退到启发式分析。
- ResultAnalyzer 2.0 支持发现类型、Top K、max/min、简单占比和 why 类问题限制说明。对于“为什么”问题，它不会从相关性结果里硬推因果，而是在 limitations 中明确说明当前 SQL result 不能证明原因。

面试表达：

> 这个设计来自需求本身：业务用户真正要的是数据答案，不是 SQL 字符串。所以我让系统执行最优候选 SQL，把结果作为可信证据返回；自然语言分析只允许基于这份结果生成，LLM 的作用是表达，不是取数。这样既让回答更饱满，也保留了 SQL 和 evidence 作为审计依据。

### 10. Feedback + Evaluation Loop

这是让项目更像真实企业系统的一层。

当前能力：

- `POST /api/v1/feedback` 支持用户反馈 SQL 和答案是否正确。
- 如果反馈中包含 corrected SQL，系统会沉淀为 verified query。
- 后续相似问题会优先召回 verified query，并加入候选 SQL 排序。
- verified query 有 `PENDING_REVIEW`、`VERIFIED`、`DEPRECATED`、`REJECTED` 生命周期和质量信号。
- 对指标定义错误的反馈可以生成语义模型更新建议，例如给指标补默认过滤条件。
- `EvaluationHarness` 支持衡量 valid rate、execution accuracy、answer grounding rate、semantic plan accuracy 和 verified query hit rate。
- Evaluation Benchmark 2.0 支持 tag-level metrics、difficulty metrics、错误归因、API case runner、demo SQLite 构造和 Markdown 报告输出。
- 新增 business benchmark：用确定性 SQLite 构造部门、员工、客户、商品、订单、订单明细、退款和站内行为 8 张表，配套 40 条业务问题和 Semantic Layer，覆盖 basic、semantic、join、trend、analysis、visualization、safety 场景。

面试表达：

> 我没有把错误处理停留在单次自纠错，而是增加了反馈和评估闭环。用户修正后的 SQL 会沉淀成 verified query，下次类似问题可以优先复用；同时我构造了可复现的 SQLite 业务 benchmark，用 valid rate、execution accuracy、answer grounding rate、tag metrics 和 difficulty metrics 衡量每次迭代是否真的变好。

### 11. 可替换 IoC 架构

项目通过 `System` 和环境变量注册实现类。

当前可替换组件：

- `LLMBackend`
- `StorageBackend`
- `VectorBackend`
- `ContextStore`
- `Evaluator`

面试表达：

> 我把 LLM、存储、向量库、上下文检索和评估器都抽象成可替换组件，业务代码依赖接口而不是具体 SDK。真实 adapter 可以通过环境变量接入，测试链路使用 MockLLM、内存存储和 SQLite benchmark 保持稳定。

### 12. 测试覆盖不是摆设

当前根目录重构版测试覆盖：

- 核心类型。
- SQL 执行。
- Agent 工具。
- Schema Linking。
- SchemaScanner。
- ConversationManager。
- API 端到端。
- IoC 注册。
- 候选 SQL Ranking。
- ResultAnalyzer grounded 输出和 LLM 回退保护。
- Semantic Layer 和 SemanticQueryPlan。
- FeedbackService 和 verified query。
- VisualizationRecommender 与 ECharts option。
- Evaluation Benchmark。
- sqlglot AST SQL 安全校验。
- business SQLite benchmark 数据集和 40 条业务评估样例。
- 自纠错。
- Evaluator。
- SQLite + MockLLM 原型端到端测试，以及真实 adapter 集成测试骨架。

最新验证结果以本地 `pytest tests -q` 为准；当前完整模块验证覆盖根目录重构版测试、business benchmark、SQL AST safety、工具层、候选排序和评估 Harness。

面试表达：

> 我为核心链路写了可重复的模块测试和 SQLite + MockLLM 端到端测试，保证不依赖真实 LLM 也能验证主流程。

## 最推荐的项目讲法

可以按这条主线讲：

1. 我先分析 Dataherald，抽取它的 Text-to-SQL 核心链路。
2. 我发现原始链路依赖框架 Agent、单轮问答较多、复杂 SQL 和执行反馈能力不足。
3. 所以我重构了一个轻量 SQL Agent：
   - 原生 ReAct。
   - Plan-and-Solve。
   - Schema Linking。
   - 多轮 Conversation。
   - DAIL/DIN 自纠错。
4. 后来参考 Data Agent 的 L2/L3 演进方向，我又加入：
   - Schema 语义增强。
   - 多候选 SQL。
   - 执行证据排序。
   - API 候选透明返回。
   - grounded 结果分析。
   - Semantic Layer。
   - Feedback + Evaluation Loop。
5. 最终系统从“LLM 生成 SQL”升级为“Agent 感知数据库、理解业务语义、调用工具、基于执行证据决策，并输出可追溯数据答案”。

## 可以直接放进简历的描述

> 基于 Dataherald 架构重构企业数据问答 Agent 原型，实现 QuestionRuntime / AgentState 状态机编排、ToolRegistry 声明式工具治理、RecoveryLoop 失败恢复、Semantic Layer 2.0 与 SemanticQueryPlan 中间表示、原生 ReAct / Plan-and-Solve 双 Agent 路由、Schema Scanner/Linking、多轮会话记忆、DIN/DAIL 风格执行反馈自纠错、sqlglot AST 安全校验、多候选 SQL 执行验证与可解释排序、grounded 结果洞察、Feedback verified query 生命周期、可消费 ECharts 可视化资产和离线 Evaluation Benchmark。系统提供 FastAPI 接口，使用 SQLite + MockLLM 完成端到端测试，并构造 40 条 business benchmark 覆盖业务语义、趋势分析、可视化和安全场景。

## 面试时可以主动展示的接口返回

重点展示 `/api/v1/question` 返回中的 `answer`、`semantic_plan`、`result`、`analysis`、`visualization`、`candidates`、`agent_state` 和 `recovery` 字段：

```json
{
  "answer": "当前查询结果为 1。",
  "sql": "SELECT COUNT(*) AS cnt FROM employees",
  "status": "VALID",
  "confidence_score": 0.85,
  "semantic_plan": {
    "intent": "metric_query",
    "metrics": ["employee_count"],
    "dimensions": [],
    "filters": [],
    "order_by": [],
    "limit": null
  },
  "result": {
    "columns": ["cnt"],
    "rows": [{"cnt": 1}],
    "row_count": 1,
    "truncated": false
  },
  "analysis": {
    "summary": "SQL 返回 1 行 1 列，核心指标 `cnt` 的值为 1。",
    "key_findings": [
      {"claim": "cnt = 1", "evidence": "SQL result: cnt = 1"}
    ],
    "limitations": ["该结论仅基于当前数据库快照。"],
    "followup_questions": ["是否需要按类别或部门进一步拆分？"]
  },
  "visualization": {
    "chart_type": "metric_card",
    "title": "员工数量是多少？",
    "spec": {"value": {"field": "cnt"}, "label": "cnt"}
  },
  "candidates": [
    {
      "sql": "SELECT COUNT(*) AS cnt FROM employees",
      "status": "VALID",
      "score": 0.85,
      "evidence": "执行成功，返回 1 行；结果列：cnt；评分构成：..."
    }
  ]
}
```

这个返回能体现三个点：

- Agent 不是黑盒。
- SQL 选择有执行证据。
- 系统能解释为什么选这条 SQL。
- 最终答案不是模型凭空生成，而是绑定到 SQL result evidence。
- 业务查询逻辑可以通过 `semantic_plan` 审查。

## 后续继续增强的高价值方向

1. 强化 Semantic Layer
   - SQL AST 级语义校验。
   - 多跳 Join 优化。
   - 语义模型 API 管理。

2. SQL AST 级权限校验
   - 已完成 alias、CTE、子查询作用域和列级白名单基础校验。
   - 后续重点是多数据库方言、行列级权限、资源限制和审计日志。

3. Schema / Semantic Memory
   - 将列语义、样本值、业务同义词写入向量库。
   - 支持中文业务词和英文表字段之间的语义召回。
   - verified query 使用向量召回替代轻量 token overlap。

4. 结果洞察增强
   - 基于 SQL 执行结果推荐图表类型。
   - 返回 ECharts/Vega-Lite spec。
   - 对多行结果生成 Top-K、异常值、分布变化等可追溯发现。

5. Agent Trace
   - 接入 Langfuse 或 LangSmith。
   - 记录每一步 Thought、Action、Observation、SQL 候选和评分证据。
