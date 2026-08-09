# SQL Agent 项目亮点梳理

## 一句话定位

这是一个参考 Dataherald 架构并结合 Data Agent 思路重构的轻量级 NL-to-SQL Agent 系统。它不是简单让 LLM 一次性生成 SQL，而是把数据库环境感知、工具调用、Schema Linking、多轮记忆、执行反馈自纠错和候选 SQL 证据化排序串成一个可测试的工程闭环。

## 面试官容易眼前一亮的亮点

### 1. 原生 ReAct + Plan-and-Solve 双 Agent 路由

项目没有直接依赖 LangChain Agent 黑盒，而是自己实现了 ReAct 的 Thought-Action-Observation 循环，并额外实现 Plan-and-Solve Agent 处理复杂 SQL。

可讲的技术点：

- 简单问题走 ReAct，减少规划成本。
- 复杂问题走 Plan-and-Solve，先分析表、JOIN、过滤、聚合和排序。
- `AgentSelector` 根据问题复杂度自动选择执行路径。
- 每一步工具调用都有中间步骤记录，方便调试和解释。

面试表达：

> 我没有把 Text-to-SQL 简单封成一次 LLM 调用，而是实现了一个可控 Agent loop。LLM 必须通过受控工具观察数据库，再基于 observation 继续推理，复杂问题则先规划再执行。

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

### 4. 工具层安全边界和白名单校验

项目的 LLM 不直接访问数据库，而是通过 `AgentToolkit` 的受控工具访问。

当前能力：

- 危险 SQL 拦截：`DROP`、`DELETE`、`UPDATE`、`TRUNCATE` 等。
- 工具层表名白名单。
- 工具层列名白名单。
- 候选 SQL 排序阶段再次进行 schema 校验。
- 缺少 `sql_metadata` 时有后备解析逻辑。

面试表达：

> 我把 LLM 约束在工具层里，所有表名、列名都必须来自扫描过的 schema。这样即使模型幻觉出不存在的表或危险 SQL，也会在执行前被拦截。

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

### 7. 多候选 SQL 证据化排序

这是当前最新增强，也是最值得重点展示的亮点。

当前能力：

- 从 Agent 主输出和中间步骤中收集候选 SQL。
- 候选 SQL 去重。
- 候选 SQL schema 白名单校验。
- 候选 SQL 执行验证。
- 收集 row count、columns、preview、error。
- 综合 schema、执行结果、问题意图和 Evaluator 分数排序。
- API 返回 `candidates`，让系统选择过程透明可解释。

面试表达：

> 系统不会盲信第一条 SQL，而是对候选 SQL 做执行验证和证据化排序。最终返回的不只是 SQL，还有候选分数、执行行数、结果列和选择依据。

### 8. 可替换 IoC 架构

项目通过 `System` 和环境变量注册实现类。

当前可替换组件：

- `LLMBackend`
- `StorageBackend`
- `VectorBackend`
- `ContextStore`
- `Evaluator`

面试表达：

> 我把 LLM、存储、向量库、上下文检索和评估器都抽象成可替换组件，业务代码依赖接口而不是具体 SDK，方便后续切 OpenAI、Azure、本地模型或不同向量库。

### 9. 测试覆盖不是摆设

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
- 自纠错。
- Evaluator。
- 真实 OpenAI/MongoDB/ChromaDB 集成测试骨架。

最新验证结果：

```text
84 passed, 3 skipped, 2 warnings
```

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
5. 最终系统从“LLM 生成 SQL”升级为“Agent 感知数据库、调用工具、基于执行证据决策”。

## 可以直接放进简历的描述

> 基于 Dataherald 架构重构 NL-to-SQL Agent 原型，实现原生 ReAct 和 Plan-and-Solve 双 Agent 路由、Schema Scanner/Linking、多轮会话记忆、DIN/DAIL 风格执行反馈自纠错，并进一步加入多候选 SQL 生成与执行证据排序机制。系统通过 IoC 支持 LLM、存储、向量库和评估器替换，提供 FastAPI 接口，使用 SQLite + MockLLM 完成端到端测试，核心模块测试 84 passed。

## 面试时可以主动展示的接口返回

重点展示 `/api/v1/question` 返回中的 `candidates` 字段：

```json
{
  "sql": "SELECT COUNT(*) AS cnt FROM employees",
  "status": "VALID",
  "confidence_score": 0.85,
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

## 后续继续增强的高价值方向

1. 真正多策略候选生成
   - conservative SQL
   - join-aware SQL
   - aggregation-first SQL
   - CTE-based SQL

2. SQL AST 级权限校验
   - alias 解析。
   - CTE 解析。
   - 子查询列级校验。
   - 聚合表达式解析。

3. Schema Memory
   - 将列语义、样本值、业务同义词写入向量库。
   - 支持中文业务词和英文表字段之间的语义召回。

4. Analysis Agent
   - SQL 执行后生成自然语言洞察。
   - 自动推荐图表类型。
   - 返回 ECharts/Vega-Lite spec。

5. Agent Trace
   - 接入 Langfuse 或 LangSmith。
   - 记录每一步 Thought、Action、Observation、SQL 候选和评分证据。
