# SQL Agent - 下一代自然语言转 SQL 引擎

本项目是一个基于 [Dataherald](https://github.com/Dataherald/dataherald) 架构分析后重构的 NL->SQL Agent 原型。项目目标不是简单复刻 Dataherald，而是抽取其核心 Text-to-SQL 链路，并围绕 Agent 控制流、多轮上下文、Schema Linking 和执行反馈自纠错做一版更轻量、更可控的重构实现。

更准确的项目定位是：**基于 Dataherald 架构反思后的轻量级 NL->SQL Agent 重构与增强实验**。它适合作为学习企业级 NL->SQL 系统架构、Agent 工具调用、数据库 Schema 理解和 LLM 自纠错闭环的工程项目。

## 项目背景

Dataherald 是一个面向企业数据问答场景的开源 NL->SQL 引擎，原始项目采用 FastAPI、LangChain、OpenAI、ChromaDB、MongoDB 等技术栈，并拆分为 Engine、Enterprise、Admin Console、Slackbot 等多个服务。

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
最终 SQL
```

完整请求链路可以理解为：

1. `POST /api/v1/question` 接收自然语言问题。
2. 系统构造 `Prompt` 和 `Conversation`。
3. `SchemaScanner` 扫描数据库表、列、主键和外键。
4. `ContextRetriever` 检索相关 Golden SQL 和管理员指令。
5. `AgentSelector` 根据问题复杂度选择 ReAct 或 Plan-and-Solve。
6. Agent 通过 `AgentToolkit` 调用数据库工具进行观察和验证。
7. LLM 输出 SQL。
8. `DAILStyleCorrector` 根据执行结果进行迭代修正。
9. API 返回 SQL、状态、中间步骤和错误信息。

## 项目结构

```text
sql_agent/
├── core/          # 数据模型、配置管理、IoC 容器
├── llm/           # LLM 抽象层，支持 OpenAI / Azure OpenAI 扩展
├── agent/         # Agent 框架，包括 ReAct、Plan-and-Solve 和自动选择器
├── context/       # 上下文管理，包括多轮对话、few-shot 检索和管理员指令
├── sql/           # 数据库层，包括 SQL 执行、Schema 扫描、Schema Linking、复杂 SQL 分解
├── correction/    # SQL 自纠错模块，包括 DIN-SQL 和 DAIL-SQL 风格修正器
├── storage/       # 存储层，包括 MongoDB 文档存储和 ChromaDB 向量存储
├── eval/          # SQL 质量评估器
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
- `ColumnMetadata`：列级元数据，包括类型、描述、主键、外键、样本值等。
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
- 后续可以扩展 Claude、Gemini、本地模型、不同向量库和不同文档数据库。

当前实现已经补齐核心组件注册，`System.instance()` 支持通过环境变量自动实例化 `LLMBackend`、`StorageBackend`、`VectorBackend`、`ContextStore` 和 `Evaluator`，并会校验自定义实现是否符合对应抽象类型。

### 3. LLM 抽象层

`sql_agent/llm/` 定义统一的 LLM 接口：

- `generate()`：生成模型回复。
- `generate_stream()`：流式生成。
- `embed()`：生成文本 embedding。
- `count_tokens()`：统计 token 数。

当前默认实现是 `OpenAILLM`，支持 OpenAI 和 Azure OpenAI 的扩展方向。Agent、向量检索和评估器都通过 `LLMBackend` 接口调用模型，而不是直接依赖具体 SDK。

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

这层体现了 Agent 的一个关键思想：LLM 不直接访问数据库，而是通过受控工具获取环境信息。当前工具层已经加入 schema 白名单校验，表名和列名必须来自 `SchemaScanner` 扫描得到的 `TableDescription`；`SqlDbQuery` 在执行前也会检查 SQL 中引用的表名，单表查询会额外校验简单列名。当环境缺少 `sql_metadata` 时，会降级使用轻量后备解析，避免核心测试被可选依赖阻断。

### 6. SQL 与 Schema 层

`sql_agent/sql/database.py` 封装 SQLAlchemy，提供 SQL 执行、表信息获取、DDL 生成和危险 SQL 拦截。

`sql_agent/sql/scanner.py` 负责扫描数据库 schema：

- 获取表和视图。
- 获取列名、类型、主键、外键。
- 采集列级样本值、低基数分类值和表行数。
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

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/question` | 自然语言转 SQL，设计上支持多轮对话和自纠错 |
| `POST` | `/api/v1/golden-sqls` | 添加 Golden SQL 示例 |
| `GET` | `/api/v1/golden-sqls` | 查询 Golden SQL 示例 |
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

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY、MONGODB_URI 等配置

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
- Agent 基类、复杂度判断和工具函数。
- SQL 注入拦截。
- 工具层 schema 白名单校验。
- SchemaScanner 列级样本值采集。
- SQL 自纠错基础校验。
- 启发式 SQL 质量评估。
- OpenAI、MongoDB、ChromaDB 真实集成测试骨架。

当前本地测试结果：

```text
81 passed, 3 skipped, 2 warnings
```

其中 3 个 skipped 是真实 OpenAI、MongoDB、ChromaDB 集成测试，默认需要设置 `RUN_REAL_INTEGRATIONS=true` 才运行。2 个 warnings 分别来自当前 FastAPI TestClient/httpx 组合的弃用提示，以及当前工作区 `.pytest_cache` 写入权限提示。

不建议直接运行：

```bash
pytest -q
```

因为仓库中包含 `services/engine/dataherald/tests` 原始 Dataherald 测试，它会被一起收集，并可能因为原始项目依赖未安装而失败。

当前环境下全仓库 `pytest -q` 会在收集 `services/engine/dataherald/tests` 时因为缺少原始子项目依赖 `sql_metadata` 而失败；这不属于根目录重构版 `sql_agent` 模块测试范围。

## 当前工程边界

当前项目已经具备清晰的核心架构和模块化实现，核心链路也已经从原型占位推进到可测试的端到端实现，但仍有一些生产化边界需要继续收敛：

1. Azure OpenAI 分支使用了 `azure_api_version`，但配置类中还需要补充该字段。
2. `SqlDbQuery` 复杂多表查询目前主要校验表名，列级白名单对 alias、聚合表达式、复杂子查询仍采取保守策略，后续可引入更稳定的 SQL AST 解析。
3. MongoDB 会话存储目前按普通 dict/datetime 写入，后续如果引入更复杂对象，需要统一序列化策略。
4. 真实 OpenAI、MongoDB、ChromaDB 集成测试已经补充，但默认跳过，需要在具备凭据和外部服务的环境中通过 `RUN_REAL_INTEGRATIONS=true` 显式执行。
5. 全仓库测试仍受 `services/engine` 原始 Dataherald 子项目依赖影响，需要单独安装该子项目依赖，或配置 pytest 默认只收集根目录重构版测试。

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
   - 用 Schema Linking 辅助多表 JOIN 路径发现。

3. **多轮对话能力**
   - 将单轮 Prompt 扩展为 Conversation。
   - 保存历史问题、历史 SQL 和执行结果。
   - 为后续问题提供上下文消歧能力。

4. **执行反馈自纠错**
   - SQL 生成后不是直接返回，而是执行验证。
   - 根据数据库报错或样本结果进行 DAIL-SQL 风格迭代修正。
   - 使用 DIN-SQL 风格 verify-then-fix 做语义层检查。

更稳妥的项目表述：

> 这是一个基于 Dataherald 架构分析后实现的下一代 NL->SQL Agent 原型，重点验证 Agent 控制流、Schema Linking、多轮上下文和执行反馈自纠错几个关键技术点。

不建议表述为：

> 完整超越 Dataherald 的生产级 NL->SQL 平台。

因为当前项目虽然已经补齐存储接入、会话持久化、API 端到端测试和安全白名单等核心工程项，但真实外部服务验证、复杂 SQL 权限校验和生产级观测治理仍需要继续完善。

## 推荐学习顺序

1. 阅读 `sql_agent/core/types.py`，理解系统中的核心数据对象。
2. 阅读 `sql_agent/sql/database.py` 和 `sql_agent/sql/scanner.py`，理解 SQL 执行和 Schema 来源。
3. 阅读 `sql_agent/agent/tools.py`，理解 Agent 如何通过工具观察数据库。
4. 阅读 `sql_agent/agent/react_agent.py`，理解原生 ReAct 推理循环。
5. 阅读 `sql_agent/agent/plan_solve_agent.py`，理解复杂 SQL 的先规划再执行。
6. 阅读 `sql_agent/sql/schema_linking.py`，理解 JOIN 路径发现。
7. 阅读 `sql_agent/context/conversation.py`，理解多轮上下文如何构造。
8. 阅读 `sql_agent/correction/dail_style.py`，理解执行反馈驱动的 SQL 修正闭环。

## 后续开发计划

优先级较高的工程任务：

- [x] 补齐 IoC 注册表，支持 `StorageBackend`、`VectorBackend`、`ContextStore`、`Evaluator` 自动实例化。
- [x] 修复 `/api/v1/question`，从存储中加载真实数据库连接。
- [x] 将 `ConversationManager` 接入全局存储或数据库，实现跨请求多轮会话。
- [x] 修复 `extract_sql_from_output()` 的异常 markdown 代码块解析问题。
- [x] 增加 SQLite + MockLLM 的 API 端到端测试。
- [x] 为工具层表名、列名增加 schema 白名单校验。
- [x] 完善 SchemaScanner 的样本值采集和列级上下文写入。
- [x] 增加真实 OpenAI、MongoDB、ChromaDB 集成测试。
- [ ] 在具备真实凭据和外部服务的环境中执行 OpenAI、MongoDB、ChromaDB 集成测试。
- [ ] 强化复杂多表 SQL 的 alias、表达式和子查询列级白名单校验。
- [ ] 统一 MongoDB 会话和复杂对象的序列化策略。
- [ ] 接入 Langfuse / LangSmith 做 Agent 推理链路追踪。
- [ ] 接入 Prometheus / Grafana 做服务监控。
- [ ] 适配更多 LLM 后端，例如 Claude、Gemini、本地模型。
- [ ] 支持更细粒度的权限控制和审计日志。

## 设计原则

- **模块可替换**：LLM、存储、向量库、评估器等组件通过接口隔离。
- **Agent 可控**：用原生 ReAct 和 Plan-and-Solve 控制推理流程，而不是完全依赖框架黑盒。
- **Schema 优先**：先理解数据库结构，再让 LLM 生成 SQL。
- **执行闭环**：生成 SQL 后通过数据库执行反馈进行修正。
- **如实演进**：保持原型边界清晰，优先打通核心链路，再补生产级能力。
