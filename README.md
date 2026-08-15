# SQL Agent - 下一代自然语言转 SQL 引擎

本项目是一个基于 [Dataherald](https://github.com/Dataherald/dataherald) 架构分析后重构的 NL->SQL Agent 原型。项目目标不是简单复刻 Dataherald，而是抽取其核心 Text-to-SQL 链路，并围绕 Agent 控制流、多轮上下文、Schema Linking 和执行反馈自纠错做一版更轻量、更可控的重构实现。

更准确的项目定位是：**基于 Dataherald 架构反思后的轻量级企业数据问答 Agent 重构与增强实验**。它不是裸 schema prompt 的 Text-to-SQL demo，而是围绕 Semantic Layer、SemanticQueryPlan、候选 SQL 执行证据、grounded 结果分析、反馈学习和离线评估闭环构建的可测试工程项目。

## 项目背景

Dataherald 是一个面向企业数据问答场景的开源 NL->SQL 引擎，原始项目采用 FastAPI、LangChain、外部 LLM、向量库、文档库等技术栈，并拆分为 Engine、Enterprise、Admin Console、Slackbot 等多个服务。

通过分析 Dataherald 的核心 Engine，可以发现它的主链路大致是：

1. 用户提交自然语言问题。
2. API 创建 Prompt 对象。
3. SQLGenerationService 调用 SQL Agent。
4. Agent 从 ContextStore 中检索 Golden SQL 示例和管理员指令。
5. Agent 使用 ReAct 工具链获取相关表、表结构、列信息和执行反馈。
6. LLM 生成 SQL。
7. 系统做语法验证并返回 SQLGeneration。

本项目在此基础上重新设计了核心引擎，重点增强以下四个方向：

| 方向 | Dataherald 原始实现 | 本项目重构思路 |
|------|--------------------|----------------|
| Agent 模式 | 依赖 LangChain ZeroShotAgent | 原生 ReAct Agent + Plan-and-Solve Agent，按复杂度自动选择 |
| 多轮对话 | 每次提问相对独立 | ConversationManager 管理历史、上下文窗口和引用消歧 |
| 复杂 SQL | 多表 JOIN、CTE、窗口函数支持有限 | Schema Linking、外键路径发现、复杂查询分解 |
| Self-Correct | 以语法验证为主 | DIN-SQL 风格语义验证 + DAIL-SQL 风格执行反馈修正 |
| 结果回答 | 主要返回 SQLGeneration | API 透出最优候选执行结果，并基于受控结果生成 grounded answer/summary/key findings |
| 业务语义 | 主要依赖数据库 schema 和说明 | Semantic Layer 2.0 显式建模指标治理字段、维度、时间粒度、同义词、默认过滤条件和简单关系 Join |
| 反馈评估 | 缺少闭环 | 用户反馈沉淀带生命周期的 verified query，Evaluation Benchmark 2.0 衡量 valid/execution/grounding/semantic/visualization 指标并输出错误归因 |

## 核心架构

项目采用分层设计，将 NL->SQL 链路拆成 API 层、上下文层、Schema 层、Agent 推理层、SQL 执行层、自纠错层和存储层。

```text
用户问题
  |
  v
FastAPI API
  |
  v
Prompt / Conversation
  |
  v
ContextRetriever
  |-- Golden SQL few-shot 示例
  |-- 管理员指令
  |
  v
SchemaScanner / SchemaLinker
  |-- 表结构扫描
  |-- 主键/外键识别
  |-- JOIN 路径发现
  |
  v
AgentSelector
  |-- ReActAgent
  |-- PlanSolveAgent
  |
  v
AgentToolkit
  |-- 查询相关表
  |-- 获取表结构
  |-- 检查列实体值
  |-- 执行 SQL
  |
  v
SQL 生成
  |
  v
DAIL / DIN Self-Correction
  |
  v
CandidateRanker
  |-- 候选 SQL 执行验证
  |-- 证据化评分排序
  |
  v
ResultAnalyzer
  |-- 透出最优候选执行结果
  |-- 启发式稳定回答
  |-- 严格 grounded 的 LLM 自然语言分析
  |
  v
最终答案 + SQL + 执行结果 + 分析证据
```

完整请求链路可以理解为：

1. `POST /api/v1/question` 接收自然语言问题。
2. 系统构造 `Prompt` 和 `Conversation`。
3. `SchemaScanner` 扫描数据库表、列、主键和外键。
4. 当配置 `SEMANTIC_MODEL_PATH` 时，`SemanticPlanner` 会把问题解析成 `SemanticQueryPlan`，并编译出语义 SQL 候选。
5. `ContextRetriever` 检索相关 Golden SQL 和管理员指令。
6. `FeedbackService` 召回历史 verified query，和语义 SQL、Agent SQL 一起进入候选集合。
7. `AgentSelector` 根据问题复杂度选择 ReAct 或 Plan-and-Solve。
8. Agent 通过 `AgentToolkit` 调用数据库工具进行观察和验证。
9. LLM 输出补充 SQL。
10. `DAILStyleCorrector` 根据执行结果进行迭代修正。
11. `CandidateRanker` 对候选 SQL 做 schema 校验、执行验证和证据化排序。
12. API 透出最优候选 SQL 的受控执行结果，包括列名、预览行数、返回行数和截断状态。
13. `ResultAnalyzer` 基于 SQL 执行结果生成 `answer`、`summary` 和带 evidence 的 `key_findings`。
14. `VisualizationRecommender` 根据结果形状生成 metric card、bar、line、table 或 pie 建议，并返回可直接消费的 ECharts option、字段校验结果和 finding 适配信息。
15. API 返回最终答案、SemanticQueryPlan、SQL、执行结果、分析证据、图表建议、中间步骤、候选证据和错误信息。

## 项目结构

```text
sql_agent/
├── core/          # 数据模型、配置管理、IoC 容器
├── llm/           # LLM 抽象层，原型默认使用本地 MockLLM
├── agent/         # Agent 框架，包括 ReAct、Plan-and-Solve 和自动选择器
├── context/       # 上下文管理，包括多轮对话、few-shot 检索和管理员指令
├── sql/           # 数据库层，包括 SQL 执行、Schema 扫描、Schema Linking、复杂 SQL 分解
├── correction/    # SQL 自纠错模块，包括 DIN-SQL 和 DAIL-SQL 风格修正器
├── ranking/       # 候选 SQL 排序、执行证据和评分选择
├── analysis/      # 基于 SQL 执行结果的稳定回答与 grounded LLM 分析
├── semantic/      # Semantic Layer、SemanticQueryPlan、语义 SQL 编译
├── feedback/      # 用户反馈、verified query 和反馈学习闭环
├── visualization/ # 基于 SQL result 的图表推荐和可视化 spec
├── security/      # 基于 sqlglot AST 的 SQL 安全校验、表/列白名单和策略报告
├── storage/       # 存储层，原型默认使用内存文档存储和内存向量检索
├── eval/          # SQL 质量评估器、离线 benchmark 和 API case runner
└── api/           # FastAPI REST 路由

main.py            # FastAPI 应用入口
tests/             # sql_agent 核心模块测试
ARCHITECTURE.md    # Dataherald 原始项目架构分析
services/          # Dataherald 原始多服务参考实现或源码镜像
```

## 核心模块说明

### 1. 数据模型层

`sql_agent/core/types.py` 定义了整个系统的数据契约，主要包括：

- `DatabaseConnection`：数据库连接配置。
- `ColumnMetadata`：列级元数据，包括类型、描述、主键、外键、样本值、语义类型、同义词和统计信息等。
- `TableDescription`：表结构描述，包括表名、schema、列信息、DDL 和扫描状态。
- `Prompt`：用户单轮自然语言问题。
- `Conversation` / `ConversationTurn`：多轮对话会话和历史轮次。
- `SQLGeneration`：SQL 生成结果，包含状态、置信度、中间步骤和纠错信息。
- `GoldenSQL`：few-shot 检索使用的黄金问答样例。
- `Instruction`：管理员定义的 SQL 生成约束。
- `AgentConfig`：Agent 路由、自纠错、最大迭代次数等配置。

这层是理解项目的入口，因为后续所有模块都围绕这些对象流转。

### 2. IoC 配置层

`sql_agent/core/config.py` 实现了一个受 Dataherald 启发的轻量 IoC 容器。核心类是 `System`，负责通过环境变量和默认实现创建组件实例。

设计目标：

- 核心组件可替换。
- LLM、存储、向量库、评估器等实现不直接写死在业务逻辑里。
- 后续可以替换真实模型、本地模型、不同向量库和不同文档数据库实现。

当前实现已经补齐核心组件注册，`System.instance()` 支持通过环境变量自动实例化 `LLMBackend`、`StorageBackend`、`VectorBackend`、`ContextStore` 和 `Evaluator`，并会校验自定义实现是否符合对应抽象类型。

### 3. LLM 抽象层

`sql_agent/llm/` 定义统一的 LLM 接口：

- `generate()`：生成模型回复。
- `generate_stream()`：流式生成。
- `embed()`：生成文本 embedding。
- `count_tokens()`：统计 token 数。

当前默认实现是 `MockLLM`，用于让原型在没有外部模型服务的情况下稳定运行和测试。Agent、向量检索和评估器都通过 `LLMBackend` 接口调用模型，而不是直接依赖具体 SDK。

### 4. Agent 推理层

`sql_agent/agent/` 是项目的核心亮点。

#### ReActAgent

`ReActAgent` 实现原生 Thought-Action-Observation 循环，不依赖 LangChain。

基本流程：

1. LLM 先输出 `Thought`，分析下一步要做什么。
2. LLM 输出 `Action`，选择工具。
3. 系统执行工具并返回 `Observation`。
4. LLM 根据观察继续推理。
5. 获得足够信息后输出最终 SQL。

这种方式相比直接让 LLM 生成 SQL 更可控，也更容易记录中间推理和调试失败原因。

#### PlanSolveAgent

`PlanSolveAgent` 面向复杂 SQL 问题，采用先规划再求解的方式。

适用场景包括：

- 多表 JOIN。
- 多层聚合。
- 排名类查询。
- 同比、环比、趋势分析。
- CTE 或窗口函数。

它会先让模型分析所需表、JOIN 条件、过滤条件、聚合方式和排序逻辑，再逐步调用工具执行计划。

#### AgentSelector

`AgentSelector` 根据问题复杂度自动选择 Agent：

- 简单问题：走 `ReActAgent`。
- 中等问题：默认仍走 `ReActAgent`。
- 复杂问题：走 `PlanSolveAgent`。

复杂度判断基于关键词、时间序列表达、JOIN/聚合意图和表数量等启发式规则。

### 5. Agent 工具层

`AgentToolkit` 将数据库能力封装为 Agent 可调用工具，包括：

- `SqlDbQuery`：执行 SQL 并返回结果。
- `SystemTime`：获取当前系统时间。
- `DbTablesWithRelevanceScores`：基于 embedding 找相关表。
- `DbRelevantTablesSchema`：获取指定表的 schema。
- `DbColumnEntityChecker`：检查某个实体值是否存在于指定列。
- `DbRelevantColumnsInfo`：获取列描述、枚举值和样本值。
- `FewshotExamplesRetriever`：获取相似 Golden SQL 示例。
- `GetAdminInstructions`：获取管理员指令。

这层体现了 Agent 的一个关键思想：LLM 不直接访问数据库，而是通过受控工具获取环境信息。当前工具层已经接入基于 `sqlglot` 的 AST 安全校验，表名和列名必须来自 `SchemaScanner` 扫描得到的 `TableDescription`；`SqlDbQuery` 在执行前会拒绝非 SELECT、多语句、未知表、未知列、歧义未限定列、受策略限制的 `SELECT *` 和危险函数。相比旧的字符串/regex 校验，AST 校验可以正确处理 alias、JOIN、CTE 和子查询作用域。

### 6. SQL 与 Schema 层

`sql_agent/sql/database.py` 封装 SQLAlchemy，提供 SQL 执行、表信息获取、DDL 生成和危险 SQL 拦截。

`sql_agent/sql/scanner.py` 负责扫描数据库 schema：

- 获取表和视图。
- 获取列名、类型、主键、外键。
- 采集列级样本值、低基数分类值和表行数。
- 采集 distinct/null 统计。
- 基于列名、类型、主外键和样本值推断列级语义类型与同义词。
- 构造 `TableDescription`。
- 生成类似 `CREATE TABLE` 的 schema 文本，并追加列样本上下文。

`sql_agent/sql/schema_linking.py` 负责 Schema Linking：

- 构建外键关系图。
- 根据外键发现 JOIN 路径。
- 将自然语言中的实体和表名、列名做简单匹配。
- 为复杂多表查询提供 JOIN 条件建议。

`sql_agent/sql/complex_sql.py` 提供复杂查询识别和分解能力，用于识别 ranking、comparison、time series、aggregation ratio 等查询类型。

### 7. 多轮对话层

`ConversationManager` 是 Dataherald 原始链路中相对缺失的一块增强能力。

它支持：

- 创建会话。
- 追加用户和助手轮次。
- 保存历史 SQL 和执行结果。
- 控制上下文窗口长度。
- 构造可注入 LLM 的对话上下文。
- 删除和列出活跃会话。

设计目标是支持类似下面的多轮问题：

```text
用户：查询 2023 年每个部门的销售额
助手：生成 SQL A
用户：那只看销售额最高的 3 个部门
助手：基于上一轮上下文生成 SQL B
```

当前模块已经支持内存态会话管理和可选存储后端。API 层使用进程级全局 `System` 和存储化 `ConversationManager`，会将会话写入 `conversations` 集合，因此同一个 `conversation_id` 可以跨请求恢复历史。

### 8. 自纠错层

`sql_agent/correction/` 实现两类 SQL 自纠错策略。

#### DIN-SQL 风格修正

`DINStyleCorrector` 采用 verify-then-fix 思路：

1. 判断当前 SQL 是否正确回答问题。
2. 如果不正确，定位错误类型。
3. 修正表名、列名、JOIN、聚合、过滤、分组等问题。
4. 再做 SQL 验证。

#### DAIL-SQL 风格修正

`DAILStyleCorrector` 采用 execute-feedback-fix 思路：

1. 尝试执行 SQL。
2. 捕获数据库错误或样本结果。
3. 将执行反馈交给 LLM。
4. 让 LLM 生成修正版 SQL。
5. 迭代直到 SQL 可执行或达到最大轮数。

这个模块体现了项目的核心工程判断：NL->SQL 不能只依赖一次性生成，必须引入数据库执行反馈，让系统形成闭环。

### 9. 评估层

`sql_agent/eval/evaluator.py` 提供两种评估思路：

- LLM 评估：从正确性、完整性、效率三个维度让模型打分。
- 启发式评估：根据 SQL 是否包含 `SELECT`、`FROM` 等基本结构给出简单分数。

后续可以接入更完整的评测集，例如 Spider、BIRD 或企业内部 Golden SQL 集合。

### 10. 候选 SQL 排序层

`sql_agent/ranking/` 将单次 SQL 输出升级为候选决策流程。

当前能力包括：

- 从 Semantic Layer、verified query、Agent 主输出和中间步骤中收集候选 SQL。
- 对候选 SQL 做规范化去重。
- 执行 `sqlglot` AST 安全校验，并把 `safety` 报告写入候选证据。
- 执行候选 SQL，收集行数、列名、结果预览和错误。
- 根据 schema 校验、执行结果、SQL 结构、问题意图、verified query 命中、semantic plan 匹配、结果形状和 Evaluator 分数综合排序。
- 返回 `score_breakdown`、`selection_reason`、`source` 和 `result_shape`，说明候选 SQL 为什么被选择或降权。
- 向 API 返回 `candidates` 字段，让最终 SQL 的选择过程可解释。
- 向结果分析层提供最优候选的执行证据，避免后续回答脱离真实数据库结果。

这层是项目从“LLM 直接生成 SQL”走向“Data Agent 基于证据决策”的关键增强。当前 API 不再只返回 SQL，还会在最优候选可执行时返回 `result` 和 `analysis`：`result` 是系统执行 SQL 得到的受控数据快照，`analysis` 则是基于该快照生成的答案摘要、关键发现、限制说明和后续问题。

结果分析遵循一个硬约束：**系统执行 SQL，LLM 只分析受控 SQL 执行结果**。默认 `RESULT_ANALYZER=heuristic`，使用启发式分析器生成稳定答案；当设置 `RESULT_ANALYZER=llm` 时，会启用 `LLMResultAnalyzer` 让回答更自然，但它必须返回 JSON，且每个关键发现必须包含可追溯到 SQL result 的 evidence。如果 LLM 输出无法解析、缺少 evidence，或回答/摘要/结论中出现 SQL result 中不存在的数值，系统会自动回退到启发式分析，避免编造结论。

### 11. Semantic Layer 与 SemanticQueryPlan

`sql_agent/semantic/` 将业务语义从裸 schema 中抽出来，显式建模：

- 指标：如 `employee_count`。
- 维度：如 `department`。
- 同义词：如“员工数”、“人数”。
- 默认过滤条件：如只统计 `status = active`。
- 指标治理信息：`version`、`owner`、`certified`。
- 时间维度和时间粒度：`day`、`month`、`quarter`、`year`。
- 简单跨表关系：通过 `relationships` 编译基础 Join。
- `SemanticQueryPlan`：指标、维度、过滤、排序和 limit 的中间表示。

当配置 `SEMANTIC_MODEL_PATH` 时，API 会优先尝试生成语义计划，并把语义计划编译成 SQL 候选。这样 SQL 不再只是 LLM 的直接输出，而是一个可解释、可校验的编译产物。当前 planner 支持多指标命中、时间粒度识别和同名指标歧义澄清；当多个指标共享同一业务词时，会返回 `NEEDS_CLARIFICATION` 和候选指标，而不是强行选择。

### 12. Feedback + Evaluation Loop

`sql_agent/feedback/` 支持用户对 SQL 和答案进行反馈。如果反馈中包含 `corrected_sql`，系统会自动沉淀为 verified query，并在后续相似问题中召回，作为候选 SQL 的高可信来源。

Feedback 2.0 增强了结构化学习信号：

- 错误原因枚举：错表、错列、错过滤、错 Join、错聚合、指标定义错误、答案不 grounded、图表错误。
- verified query 生命周期：`PENDING_REVIEW`、`VERIFIED`、`DEPRECATED`、`REJECTED`。
- 质量信号写入 verified query，CandidateRanker 可据此识别 verified 来源并加分。
- 对指标定义错误的反馈生成语义模型更新建议，例如建议给指标增加默认过滤条件；系统只产出建议，不自动修改语义模型。

新增 API：

- `POST /api/v1/feedback`
- `GET /api/v1/feedback`
- `GET /api/v1/verified-queries`

`sql_agent/eval/harness.py` 提供离线评估框架，支持从 case YAML 中衡量 SQL 可执行率、执行结果准确率、答案 grounded 率、Semantic plan 命中率和 verified query 命中率。Evaluation Benchmark 2.0 进一步支持 tag-level metrics、difficulty metrics、`SEMANTIC_MISS` / `SQL_INVALID` / `EXECUTION_MISMATCH` / `UNGROUNDED_ANSWER` / `MISSING_EVIDENCE` / `WRONG_VISUALIZATION` 错误归因，以及 `sql_agent/eval/run_api_cases.py` 批量调用 `/api/v1/question` 并生成 `docs/eval-reports/<timestamp>.md`。

本次新增的 business benchmark 位于 `eval_cases/business_benchmark.yml`，配套语义模型是 `eval_cases/business_semantic_model.yml`。`sql_agent/eval/demo_business.py` 会构造确定性的 SQLite 业务数据库，包含部门、员工、客户、商品、订单、订单明细、退款和站内行为 8 张表。benchmark 共 40 条问题，覆盖 basic、semantic、join、trend、analysis、visualization 和 safety 场景，前 10 条带可执行 `golden_sql`，用于验证原型环境下的业务 SQL 口径。

### 13. Visualization Spec

`sql_agent/visualization/` 基于 SQL result 的结构推荐图表：

- 单行单列：`metric_card`
- 分类字段 + 数值字段：`bar`
- 时间字段 + 数值字段：`line`
- 其他明细：`table`
- 占比或份额问题：`pie`

每个推荐会同时返回轻量 spec 和可直接消费的 ECharts option，并做字段校验：x/y 字段必须存在，y 必须是数值，趋势图 x 必须是时间字段。推荐结果还会标记是否支持当前 key finding，让前端可以把文字洞察和图表资产绑定展示。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/question` | 自然语言数据问答，返回答案、SQL、执行结果、grounded 分析、候选证据，并支持多轮对话和自纠错 |
| `POST` | `/api/v1/golden-sqls` | 添加 Golden SQL 示例 |
| `GET` | `/api/v1/golden-sqls` | 查询 Golden SQL 示例 |
| `POST` | `/api/v1/feedback` | 提交查询反馈，corrected SQL 会沉淀为 verified query |
| `GET` | `/api/v1/feedback` | 查询反馈记录 |
| `GET` | `/api/v1/verified-queries` | 查询沉淀出的 verified query |
| `POST` | `/api/v1/database-connections` | 添加数据库连接 |
| `GET` | `/api/v1/database-connections` | 列出数据库连接 |
| `POST` | `/api/v1/database-connections/{id}/scan` | 扫描数据库 Schema |
| `GET` | `/api/v1/table-descriptions/{db_id}` | 查询表结构描述 |
| `GET` | `/api/v1/conversations` | 查看活跃对话 |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | 删除会话 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 可选配置环境变量
# 默认使用 MockLLM + 内存存储 + SQLite benchmark，不需要外部服务凭据

# 3. 启动服务
python main.py

# 4. 访问 API 文档
# http://localhost:8000/docs
# http://localhost:8000/api/v1/health
```

## 测试状态

当前建议只运行根目录下的重构版测试：

```bash
pytest -q tests
```

当前测试覆盖方向：

- 核心数据模型。
- SQL 执行、JOIN、聚合、子查询和三表 JOIN。
- Schema Linking 和 JOIN 路径发现。
- ConversationManager 多轮上下文构造。
- FastAPI `/api/v1/question` + SQLite + MockLLM 端到端链路。
- 候选 SQL 执行验证、证据化评分和排序。
- 最优候选执行结果 API 透出。
- 启发式 ResultAnalyzer 和严格 grounded 的 LLMResultAnalyzer。
- Semantic Layer、SemanticQueryPlan、语义 SQL 编译。
- FeedbackService、verified query 沉淀和召回。
- VisualizationRecommender 图表推荐、ECharts option 和字段校验。
- Evaluation Harness 离线指标评估。
- API benchmark runner 和 Markdown 评估报告生成。
- business SQLite benchmark 数据集、语义模型和 40 条业务评估样例。
- sqlglot AST SQL 安全校验，包括 alias、JOIN、CTE、子查询作用域、未知表/列和多语句拦截。
- Agent 基类、复杂度判断和工具函数。
- SQL 注入拦截。
- 工具层 schema 白名单校验。
- SchemaScanner 列级样本值采集。
- SQL 自纠错基础校验。
- 启发式 SQL 质量评估。
- SQLite + MockLLM 原型端到端测试。

当前本地测试结果以最新 `pytest tests -q` 输出为准。当前工作区 `.pytest_cache` 可能因为本机权限设置出现写入 warning，不影响功能断言。

不建议直接运行：

```bash
pytest -q
```

因为仓库中包含 `services/engine/dataherald/tests` 原始 Dataherald 测试，它会被一起收集，并可能因为原始项目依赖未安装而失败。

当前环境下全仓库 `pytest -q` 仍可能收集 `services/engine/dataherald/tests` 原始子项目测试；这不属于根目录重构版 `sql_agent` 模块测试范围。

## 当前工程边界

当前项目已经具备清晰的核心架构和模块化实现，核心链路也已经从原型占位推进到可测试的端到端实现，但仍有一些生产化边界需要继续收敛：

1. SQL AST 安全校验已经覆盖常见 SELECT、JOIN、alias、CTE 和子查询场景，但还不是完整数据库权限系统；生产环境仍需要叠加数据库只读账号、行列级权限、审计日志和查询资源限制。
2. 候选 SQL 当前主要来自 Agent 主输出和中间步骤，后续可以扩展为多策略主动生成候选。
3. `LLMResultAnalyzer` 当前主要校验 evidence 和数值事实可追溯性，复杂自然语言因果解释仍应保持在 limitations 中，不能当成数据库外的事实判断。
4. Semantic planner 当前是启发式匹配，SQL compiler 支持多指标、简单维度、默认过滤、Top-K、时间粒度和一跳关系 Join，但还不是完整语义 SQL 编译器。
5. Verified query 召回使用轻量 token overlap，后续可以接更真实的语义召回；生命周期目前是数据结构和 API 层能力，还没有人工审核 UI。
6. 当前默认使用 MockLLM、内存存储和 SQLite benchmark，定位是可复现原型，不是生产级外部服务集成平台。
7. 全仓库测试仍可能受 `services/engine` 原始 Dataherald 子项目影响，建议默认只运行根目录重构版测试。

这些边界不影响项目作为学习和展示 Agent 架构的价值，但在面试或简历中应如实表述为“原型系统”和“核心链路重构”，不要包装成完整生产级平台。

## 秋招项目表达建议

可以将该项目概括为：

> 我分析了开源 NL->SQL 项目 Dataherald 的架构，发现其核心链路依赖 LangChain ZeroShotAgent，每次查询相对独立，对复杂 SQL 和自纠错支持有限。因此我抽取核心 NL->SQL 引擎，重构了一个轻量级 SQL Agent 原型，实现了原生 ReAct、Plan-and-Solve、多轮对话管理、Schema Linking 和执行反馈自纠错。

面试时可以重点讲四个技术点：

1. **Agent 控制流重构**
   - 不直接依赖 LangChain Agent。
   - 自己实现 Thought-Action-Observation 循环。
   - 支持按复杂度自动选择 ReAct 或 Plan-and-Solve。

2. **Schema 理解增强**
   - 使用 SQLAlchemy inspector 扫描表、列、主键和外键。
   - 构建外键关系图。
   - 采集样本值、distinct/null 统计、语义类型和同义词。
   - 用 Schema Linking 辅助多表 JOIN 路径发现。

3. **多轮对话能力**
   - 将单轮 Prompt 扩展为 Conversation。
   - 保存历史问题、历史 SQL 和执行结果。
   - 为后续问题提供上下文消歧能力。

4. **执行反馈自纠错**
   - SQL 生成后不是直接返回，而是执行验证。
   - 根据数据库报错或样本结果进行 DAIL-SQL 风格迭代修正。
   - 使用 DIN-SQL 风格 verify-then-fix 做语义层检查。

5. **候选 SQL 证据化排序**
   - 收集候选 SQL。
   - 对候选做 schema 校验和真实执行。
   - 根据执行证据、问题意图和评估分选择最优 SQL。

6. **Grounded 结果分析**
   - API 透出最优候选 SQL 的执行结果。
   - 默认用启发式分析器生成稳定答案。
   - 可选 LLM 分析器只消费 SQL result，不接触数据库连接。
   - 关键发现必须带 SQL result evidence，异常或不可信输出自动回退。

7. **Semantic Layer + Feedback + Evaluation**
   - 指标、维度、同义词、默认过滤条件、指标 owner/version/certified、时间粒度和简单关系通过 YAML 语义模型显式定义。
   - 用户问题先解析为 `SemanticQueryPlan`，SQL 是可校验计划的编译结果；多指标和歧义场景可以结构化表达。
   - 用户反馈可沉淀为带生命周期和质量信号的 verified query，后续相似问题优先复用并进入 CandidateRanker 加分。
   - Evaluation Benchmark 衡量 valid rate、execution accuracy、answer grounding rate、semantic plan accuracy、tag metrics 和错误归因。

更稳妥的项目表述：

> 这是一个基于 Dataherald 架构分析后实现的下一代 NL->SQL Agent 原型，重点验证 Agent 控制流、Schema Linking、多轮上下文和执行反馈自纠错几个关键技术点。

不建议表述为：

> 完整超越 Dataherald 的生产级 NL->SQL 平台。

因为当前项目虽然已经补齐存储接入、会话持久化、API 端到端测试和安全白名单等核心工程项，但复杂 SQL 权限校验和生产级观测治理仍需要继续完善。

## 推荐学习顺序

1. 阅读 `sql_agent/core/types.py`，理解系统中的核心数据对象。
2. 阅读 `sql_agent/sql/database.py` 和 `sql_agent/sql/scanner.py`，理解 SQL 执行和 Schema 来源。
3. 阅读 `sql_agent/agent/tools.py`，理解 Agent 如何通过工具观察数据库。
4. 阅读 `sql_agent/agent/react_agent.py`，理解原生 ReAct 推理循环。
5. 阅读 `sql_agent/agent/plan_solve_agent.py`，理解复杂 SQL 的先规划再执行。
6. 阅读 `sql_agent/sql/schema_linking.py`，理解 JOIN 路径发现。
7. 阅读 `sql_agent/context/conversation.py`，理解多轮上下文如何构造。
8. 阅读 `sql_agent/correction/dail_style.py`，理解执行反馈驱动的 SQL 修正闭环。
9. 阅读 `sql_agent/ranking/ranker.py`，理解候选 SQL 如何基于执行证据排序。
10. 阅读 `sql_agent/analysis/result_analyzer.py`，理解系统如何把 SQL result 转成稳定、可追溯的自然语言答案。
11. 阅读 `sql_agent/semantic/`，理解 Semantic Layer 如何把业务口径变成可校验计划。
12. 阅读 `sql_agent/feedback/` 和 `sql_agent/eval/harness.py`，理解反馈学习和离线评估闭环。

## 后续开发计划

优先级较高的工程任务：

- [x] 补齐 IoC 注册表，支持 `StorageBackend`、`VectorBackend`、`ContextStore`、`Evaluator` 自动实例化。
- [x] 修复 `/api/v1/question`，从存储中加载真实数据库连接。
- [x] 将 `ConversationManager` 接入全局存储或数据库，实现跨请求多轮会话。
- [x] 修复 `extract_sql_from_output()` 的异常 markdown 代码块解析问题。
- [x] 增加 SQLite + MockLLM 的 API 端到端测试。
- [x] 为工具层表名、列名增加 schema 白名单校验。
- [x] 完善 SchemaScanner 的样本值采集和列级上下文写入。
- [x] 将默认运行链路收敛为 MockLLM、内存存储和 SQLite benchmark，不依赖外部服务。
- [x] 增加候选 SQL 执行验证、证据化评分和排序。
- [x] 将最优候选 SQL 的执行结果透出到 `/api/v1/question`。
- [x] 增加启发式 `ResultAnalyzer`，生成稳定的 `answer`、`summary` 和 `key_findings`。
- [x] 接入严格 grounded 的 `LLMResultAnalyzer`，自然语言回答必须基于 SQL result，异常输出自动回退。
- [x] 增加 Semantic Layer，支持指标、维度、同义词和默认过滤条件。
- [x] 增加 `SemanticQueryPlan` 中间表示和语义 SQL 编译。
- [x] 增加 Feedback API，将 corrected SQL 沉淀为 verified query。
- [x] 增加 Evaluation Harness，衡量 valid/execution/grounding/semantic plan 指标。
- [x] 增加 VisualizationRecommender，返回 metric card、bar、line、table spec。
- [x] 为 SchemaScanner 增加列级语义类型、同义词和统计信息。
- [x] Semantic Layer 2.0：支持指标治理字段、多指标、时间粒度、简单关系 Join 和歧义澄清。
- [x] Feedback 2.0：支持结构化错误原因、verified query 生命周期、质量信号和语义模型更新建议。
- [x] CandidateRanker 2.0：支持评分拆解、候选来源、选择理由、结果形状校验、verified query bonus 和 semantic plan match bonus。
- [x] ResultAnalyzer 2.0：支持发现类型、Top K、比较、占比和 why 类问题限制说明。
- [x] Visualization 2.0：支持 ECharts option、字段校验、finding 适配和占比场景 pie chart。
- [x] Evaluation Benchmark 2.0：支持 API case runner、demo SQLite、tag metrics、错误归因和 Markdown 报告输出。
- [ ] 扩展多策略候选 SQL 主动生成。
- [x] 增加图表推荐和可视化 spec 输出，让结果分析进一步从文本答案扩展到可展示洞察。
- [x] 增加基于 `sqlglot` 的 SQL AST 安全校验，覆盖 alias、CTE、子查询、未知表/列、歧义列和多语句拦截。
- [x] 增加 SQLite business benchmark 数据集、业务语义模型和 40 条业务评估样例。
- [ ] 继续强化 AST 安全策略的数据库方言覆盖、行列权限和查询资源限制。
- [ ] 接入 Langfuse / LangSmith 做 Agent 推理链路追踪。
- [ ] 接入 Prometheus / Grafana 做服务监控。
- [ ] 适配真实模型或本地模型后端。
- [ ] 支持更细粒度的权限控制和审计日志。

## 设计原则

- **模块可替换**：LLM、存储、向量库、评估器等组件通过接口隔离。
- **Agent 可控**：用原生 ReAct 和 Plan-and-Solve 控制推理流程，而不是完全依赖框架黑盒。
- **Schema 优先**：先理解数据库结构，再让 LLM 生成 SQL。
- **执行闭环**：生成 SQL 后通过数据库执行反馈进行修正。
- **答案可追溯**：最终自然语言答案只能来自系统执行 SQL 得到的受控结果，SQL 和 evidence 保留为审计依据。
- **业务语义显式化**：指标、维度、默认过滤条件、指标治理信息、时间粒度和简单关系进入 Semantic Layer，SQL 是可校验计划的编译结果。
- **反馈可沉淀**：用户修正可以进入 verified query，参与后续候选召回和排序。
- **如实演进**：保持原型边界清晰，优先打通核心链路，再补生产级能力。
