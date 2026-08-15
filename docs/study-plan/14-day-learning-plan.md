# 两周吃透 SQL Agent 项目学习计划

## 总目标

用 14 天、每天 3-4 小时，系统掌握本项目的架构、技术栈、源码细节、测试设计和面试表达。最终达到：面试官从项目背景、技术选型、源码实现、测试策略、系统风险和后续优化任意方向追问时，都能有结构地回答。

## Day 1：项目全局地图和 Dataherald 对照

**目标：** 建立全局认知，知道这个项目为什么存在，以及相比 Dataherald 改了什么。

**阅读：**

- `README.md`
- `ARCHITECTURE.md`
- `requirements.txt`
- `main.py`

**命令：**

```bash
pytest -q tests
rg -n "^class |^def |^async def " sql_agent tests main.py
```

**必须理解：**

- `services/` 是 Dataherald 原始多服务参考实现或源码镜像。
- `sql_agent/` 是当前重构出来的核心 NL->SQL Agent 引擎。
- 本项目不是完整生产平台，而是核心 Agent 引擎重构原型。
- 当前核心增强点：Semantic Layer 业务语义治理、原生 Agent、多轮对话、Schema Linking、自纠错、候选 SQL 可解释排序、grounded 结果洞察、ECharts 可视化资产和 Evaluation Benchmark。

**当日产出：**

- 画出“NL->SQL 主链路图”。
- 写一段 2 分钟口述稿：为什么参考 Dataherald，但不直接复刻。

**自测问题：**

- Dataherald 原始架构包含哪些服务？
- 为什么本项目重点放在 `sql_agent`？
- 当前测试结果说明了什么？测试目录覆盖什么？
- Dataherald 的 Engine、Enterprise、Admin Console、Slackbot 分别解决什么问题？
- 如果面试官问“你做的是 Dataherald 还是自己的项目”，你如何回答？
- `README.md` 中提到的四个增强点分别对应哪些代码目录？
- `services/` 目录为什么不应该作为你面试时的主要实现成果来讲？
- `sql_agent/` 和 `services/engine/dataherald/` 的关系是什么？
- NL->SQL 系统和普通 CRUD 后端最大的区别是什么？
- 为什么自然语言转 SQL 需要 Agent，而不是一次 LLM 调用？
- 为什么项目定位要说“核心引擎重构原型”，而不是“生产级平台”？
- `pytest -q tests` 中 warnings 可能代表什么？
- `rg -n "^class |^def |^async def " sql_agent tests main.py` 能帮助你看到什么？
- 如果让你 1 分钟介绍这个项目，你会保留哪三个关键词？
- 如果让你 5 分钟介绍这个项目，你会按什么顺序展开？
- 本项目的主链路里，哪个模块最能体现“Agent”思想？
- 本项目的主链路里，哪个模块最能体现“数据库工程”能力？
- 本项目的主链路里，哪个模块最能体现“LLM 应用工程”能力？
- 你如何向非技术面试官解释 NL->SQL 的业务价值？

## Day 2：Python 后端基础和核心数据模型

**目标：** 补齐阅读源码所需的 Python 工程基础。

**阅读：**

- `sql_agent/core/types.py`
- `tests/test_core_types.py`

**复习点：**

- `dataclass`
- `Enum`
- `ABC`
- 类型注解：`Optional`、`List`、`Dict`
- 同步函数、异步函数、异常处理、依赖注入

**命令：**

```bash
pytest -q tests/test_core_types.py
```

**必须理解：**

- `DatabaseConnection`：数据库连接配置。
- `TableDescription`：数据库表结构描述。
- `Prompt`：单轮用户问题。
- `Conversation`：多轮会话。
- `SQLGeneration`：SQL 生成结果。
- `GoldenSQL`：few-shot 示例。
- `Instruction`：管理员规则。
- `AgentConfig`：Agent 执行配置。

**当日产出：**

- 画“核心数据模型关系图”。
- 写数据对象速查表：类名、职责、关键字段、使用位置。

**自测问题：**

- 为什么用 dataclass，而不是普通 dict？
- `Prompt` 和 `Conversation` 的边界是什么？
- `SQLGeneration` 为什么要保存中间步骤和纠错信息？
- `dataclass` 默认会帮我们生成哪些方法？
- `field(default_factory=...)` 解决了什么问题？
- 为什么列表字段不应该直接写成 `turns: List[...] = []`？
- `Optional[str]` 和 `str = ""` 在语义上有什么区别？
- `SQLStatus` 为什么适合用 Enum 表示？
- `ConversationTurn.role` 为什么需要区分 user、assistant、system？
- `DatabaseConnection.schemas` 的作用是什么？
- `ColumnMetadata.is_primary_key` 和 `is_foreign_key` 分别影响后续哪些模块？
- `foreign_key_ref` 为什么用字符串引用，优缺点是什么？
- `TableDescription.table_schema` 和 `columns` 是否重复？为什么两个都需要？
- `GoldenSQL.complexity` 可以如何辅助 Agent 选择？
- `Instruction` 和 `GoldenSQL` 都是上下文，它们区别是什么？
- `LLMConfig.temperature` 为什么在 NL->SQL 场景通常设为 0？
- `AgentConfig.max_iterations` 过大或过小分别有什么风险？
- `SQLGeneration.sql_before_correction` 对排查问题有什么价值？
- 如果未来要支持租户隔离，你会在哪些数据模型里补字段？
- 如果未来要支持自然语言回答 `NLGeneration`，它和 SQLGeneration 如何关联？
- 哪些字段是“业务状态”，哪些字段是“调试观测信息”？

## Day 3：FastAPI 和 API 主链路

**目标：** 吃透 HTTP 请求如何进入系统。

**阅读：**

- `main.py`
- `sql_agent/api/routes.py`
- `tests/test_api_e2e.py`

**命令：**

```bash
pytest -q tests/test_api_e2e.py
```

**必须理解：**

- `create_app()` 如何创建 FastAPI 应用。
- router 如何挂载到 `/api/v1`。
- `QuestionRequest` 和 `SQLResponse` 的字段含义。
- `/api/v1/question` 如何串起系统主链路。
- 数据库连接、Golden SQL、schema 扫描、conversation API 的职责。

**当日产出：**

- 画 `/api/v1/question` 时序图。
- 写 3 分钟口述稿：从 HTTP 请求到 SQLResponse。

**自测问题：**

- API 层为什么不应该直接实现 Agent 推理？
- 错误时如何用 `HTTPException` 返回？
- 端到端测试如何替代真实 LLM 和真实数据库？
- `create_app()` 为什么比直接在全局写所有配置更清晰？
- FastAPI 的 router prefix `/api/v1` 有什么意义？
- `QuestionRequest` 中 `conversation_id` 为空和不为空分别代表什么？
- `QuestionRequest.agent_mode` 为什么允许用户强制指定？
- `enable_correction` 为什么要暴露为请求参数？
- `/api/v1/question` 为什么需要先加载数据库连接？
- 如果 `db_connection_id` 不存在，API 应该返回什么状态码？为什么？
- schema 扫描放在请求链路中有什么优缺点？
- 为什么生产环境可能需要缓存 schema 扫描结果？
- Golden SQL 添加接口和问题生成接口之间有什么关系？
- `/database-connections/{id}/scan` 和 `/question` 中的扫描逻辑有什么不同？
- API 响应中的 `intermediate_steps` 对前端或调试有什么价值？
- 为什么 `SQLResponse.error` 不应该直接暴露敏感数据库信息？
- 如果 API 请求超时，可能卡在哪些模块？
- 如何给 `/api/v1/question` 增加 trace_id？
- FastAPI 自动生成 Swagger 对学习和调试有什么帮助？
- `tests/test_api_e2e.py` 如何验证 conversation history？
- 如果面试官让你画 API 主链路，你会画哪些节点？

## Day 4：IoC 容器和可替换组件

**目标：** 理解项目的组件可替换架构。

**阅读：**

- `sql_agent/core/config.py`
- `.env.example`
- `tests/test_ioc_registry.py`
- `tests/fakes.py`

**命令：**

```bash
pytest -q tests/test_ioc_registry.py
```

**必须理解：**

- `Settings` 从环境变量读取配置。
- `Component` 是所有可注入组件的基类。
- `System.instance()` 负责懒加载和缓存组件实例。
- `LLMBackend`、`StorageBackend`、`VectorBackend`、`ContextStore`、`Evaluator` 可以被替换。
- fake 组件如何在测试中替代外部依赖。

**当日产出：**

- 画“IoC 组件实例化流程图”。
- 写“组件接口 -> 默认实现 -> 环境变量”表格。

**自测问题：**

- 如果要把 MockLLM 换成真实模型，需要改哪里？
- 为什么 IoC 比直接在业务代码里实例化具体 LLM 更好？
- 自定义实现类型不匹配时应该如何报错？
- `Settings` 读取环境变量有哪些默认值？
- `Component.start()` 和 `Component.stop()` 的作用是什么？
- `System.instance()` 为什么要缓存实例？
- 如果每次请求都新建 LLM client，会有什么问题？
- `_COMPONENT_REGISTRY` 和 `_DEFAULT_IMPLS` 各自负责什么？
- `get_class()` 如何通过字符串导入 Python 类？
- `get_fqn()` 为什么需要返回 fully qualified name？
- 环境变量配置错类路径时，系统应该在什么时候失败？
- 为什么 fake 组件也要继承真实抽象接口？
- 测试中如何用 monkeypatch 替换环境变量？
- IoC 对单元测试有什么帮助？
- IoC 对生产部署有什么帮助？
- 如果要支持新的模型后端，你会新增哪个类，配置哪个环境变量？
- 如果要把内存文档存储替换成持久化存储，你会改哪层？
- 如果组件初始化失败，API 层应该如何处理？
- IoC 容器和依赖注入框架有什么相似与不同？
- 当前 IoC 设计是否线程安全？生产环境需要考虑什么？
- 如何避免在业务代码里出现大量具体实现类 import？

## Day 5：SQLAlchemy 和数据库执行层

**目标：** 掌握数据库连接、SQL 执行和危险 SQL 拦截。

**阅读：**

- `sql_agent/sql/database.py`
- `tests/conftest.py`
- `tests/test_sql_database.py`
- `tests/test_integration.py`

**命令：**

```bash
pytest -q tests/test_sql_database.py tests/test_integration.py
```

**必须理解：**

- `SQLDatabase.get_sql_engine()` 如何根据连接串创建 SQLAlchemy engine。
- `SQLDatabase.run_sql()` 的返回结构。
- `parser_to_filter_commands()` 如何拦截危险 SQL。
- 测试中 SQLite 内存库如何构造部门、员工、产品、销售数据。

**当日产出：**

- 写“SQL 执行层问答卡片”。
- 手写 3 个 SQL：单表查询、JOIN、子查询，并解释返回结构。

**自测问题：**

- 为什么限制 `DROP`、`DELETE`、`UPDATE`？
- 当前 SQL 安全策略有什么局限？
- 为什么测试用 SQLite 内存库？
- `create_engine()` 创建的是什么对象？
- `engine.connect()` 和直接执行 SQL 字符串有什么区别？
- SQLAlchemy 的 `text()` 解决什么问题？
- `run_sql(query, top_k)` 中 `top_k` 的作用是什么？
- `run_sql()` 为什么返回执行后的 query 和结果 dict？
- 结果 dict 中 `columns`、`result`、`row_count` 分别给谁用？
- 为什么 NL->SQL 场景一般应该只允许 SELECT？
- 当前正则拦截 SQL 危险命令可能漏掉哪些情况？
- 为什么生产环境还需要只读数据库账号？
- SQL 注入和 LLM 生成危险 SQL 是同一个问题吗？
- `get_tables_and_views()` 为什么要同时取表和视图？
- `get_table_ddl()` 对 LLM 有什么帮助？
- SQLite、PostgreSQL、MySQL 的方言差异可能影响哪些代码？
- 测试数据里的 departments、employees、products、sales 如何构成业务场景？
- JOIN 测试验证了什么能力？
- 聚合测试验证了什么能力？
- 子查询测试验证了什么能力？
- 如果 SQL 执行返回大量行，会带来什么风险？
- 如果执行 SQL 报错，错误应该传给哪个模块用于修正？
- 面试官问“你如何保证 SQL 安全”，你如何分层回答？

## Day 6：SchemaScanner 和数据库结构理解

**目标：** 理解系统如何自动发现数据库结构。

**阅读：**

- `sql_agent/sql/scanner.py`
- `tests/test_schema_scanner_samples.py`

**命令：**

```bash
pytest -q tests/test_schema_scanner_samples.py
```

**必须理解：**

- SQLAlchemy inspector 如何获取表、列、主键、外键。
- `SchemaScanner` 如何生成 `TableDescription`。
- 样本值、低基数分类值和表行数为什么对 NL->SQL 有用。
- `table_schema` 如何为 LLM 提供结构上下文。

**当日产出：**

- 画“数据库真实 schema -> TableDescription”的转换图。
- 写 2 分钟口述稿：SchemaScanner 如何减少 LLM 幻觉。

**自测问题：**

- 为什么 NL->SQL 必须先做 Schema 扫描？
- 样本值为什么能帮助实体匹配？
- 为什么只靠 embedding 找表不够？
- SQLAlchemy inspector 能获取哪些 schema 信息？
- `get_columns()` 返回的信息如何转成 `ColumnMetadata`？
- 主键对 SQL 生成有什么帮助？
- 外键对 JOIN 路径发现有什么帮助？
- 如果数据库没有声明外键，SchemaScanner 会缺失什么能力？
- `row_count` 对 Agent 或评估有什么潜在用途？
- 什么是低基数字段？为什么适合提取 categories？
- 样本值采集数量太多会有什么问题？
- 样本值采集数量太少会有什么问题？
- `table_schema` 里为什么要包含类似 CREATE TABLE 的文本？
- 给 LLM 看结构化 JSON schema 和 DDL 文本各有什么优缺点？
- 扫描视图和扫描表有什么区别？
- schema 扫描失败时系统应该如何降级？
- schema 扫描结果是否应该每次请求重新生成？为什么？
- 如何设计 schema 缓存失效策略？
- 面试官问“LLM 幻觉列名怎么办”，SchemaScanner 能提供哪部分答案？
- `tests/test_schema_scanner_samples.py` 重点验证了什么？
- 如果列里有敏感样本值，采集时应如何处理？
- 大表上采样会不会影响数据库性能？如何避免？
- SchemaScanner 和 SchemaLinker 的职责边界是什么？

## Day 7：Schema Linking 和复杂 SQL

**目标：** 掌握 JOIN 路径发现和复杂 SQL 分类。

**阅读：**

- `sql_agent/sql/schema_linking.py`
- `sql_agent/sql/complex_sql.py`
- `tests/test_schema_linking.py`
- `tests/test_complex_sql.py`

**命令：**

```bash
pytest -q tests/test_schema_linking.py tests/test_complex_sql.py
```

**必须理解：**

- `SchemaLinker` 如何构建 adjacency graph。
- `find_join_paths()` 如何根据外键找 JOIN 条件。
- `find_join_path_between_tables()` 如何用 BFS 找路径。
- `ComplexSQLDecomposer` 如何判断 ranking、comparison、time_series 等复杂问题。

**当日产出：**

- 画 employees、departments、sales、products 外键关系图。
- 写复杂 SQL 类型表。

**自测问题：**

- 多表 JOIN 为什么是 NL->SQL 难点？
- BFS 找路径有什么优点和限制？
- 如果 schema linking 找不到路径，系统应该如何降级？
- `adjacency` 图的数据结构是什么？
- 为什么表关系适合表示成图？
- 外键方向会影响 JOIN 路径发现吗？
- `find_join_paths()` 和 `find_join_path_between_tables()` 有什么区别？
- `foreign_key_ref` 的格式不统一时会有什么风险？
- 如果两个表之间有多条路径，应该如何选择？
- 如果 JOIN 路径经过中间表，LLM 需要知道什么信息？
- Schema Linking 和 embedding 相关表召回分别解决什么问题？
- `find_entity_in_schema()` 如何匹配表名和列名？
- 自然语言实体和列名不一致时可能出现什么问题？
- ComplexSQLDecomposer 如何判断 time_series？
- ComplexSQLDecomposer 如何判断 ranking？
- 复杂度启发式关键词有什么语言覆盖问题？
- 中文问题“各部门销售额排名前三”会触发哪些复杂 SQL 特征？
- CTE、子查询、窗口函数分别适合什么场景？
- 如果用户问同比/环比，SQL 中通常需要哪些日期处理？
- 如果 schema 没有日期字段，time_series 问题应该如何反馈？
- `tests/test_schema_linking.py` 的 BFS 测试证明了什么？
- 为什么多表 JOIN 错误往往不会语法报错，但语义会错？
- 面试官问“Schema Linking 的核心创新是什么”，你怎么答？

## Day 8：Agent 基类和复杂度路由

**目标：** 理解 Agent 抽象接口和自动路由。

**阅读：**

- `sql_agent/agent/base.py`
- `sql_agent/agent/agent_selector.py`
- `tests/test_agent_base.py`

**命令：**

```bash
pytest -q tests/test_agent_base.py
```

**必须理解：**

- `SQLAgent` 规定 `generate_sql()` 和 `stream_sql()`。
- `StepResult` 保存中间推理步骤。
- `AgentResult` 保存最终 SQL、状态、步骤、错误和 token。
- `estimate_complexity()` 根据关键词和表数量判断复杂度。
- `AgentSelector` 自动选择 ReAct 或 Plan-and-Solve。

**当日产出：**

- 画“AgentSelector 路由决策图”。
- 写 5 个自然语言问题，并判断会走哪个 Agent。

**自测问题：**

- 为什么复杂问题走 Plan-and-Solve？
- 启发式复杂度规则有什么不足？
- `AgentResult.steps` 为什么对调试有帮助？
- `SQLAgent` 为什么设计成抽象基类？
- `generate_sql()` 的入参为什么需要 `table_descriptions`？
- `generate_sql()` 的入参为什么需要 `few_shot_examples` 和 `instructions`？
- `stream_sql()` 当前价值是什么？未来可以如何扩展？
- `StepResult.thought`、`action`、`action_input`、`observation` 分别对应 ReAct 哪一步？
- `AgentResult.status` 和 `SQLGeneration.status` 有什么关系？
- `tokens_used` 可以用于哪些监控或成本控制？
- `estimate_complexity()` 中哪些关键词代表聚合？
- 哪些关键词代表时间序列？
- 为什么表数量也会影响复杂度？
- 如果用户问题很短但实际很复杂，启发式会漏判吗？
- 如果用户问题包含 “top” 但只是简单排序，是否一定复杂？
- `extract_sql_from_output()` 为什么要支持 markdown SQL 代码块？
- 如果 LLM 不按格式输出 SQL，系统如何兜底？
- `truncate_observation()` 为什么重要？
- 复杂度路由是否应该由 LLM 判断？优缺点是什么？
- 如果用户强制 `agent_mode=react`，系统是否还应该自动切换？
- 面试官问“AgentSelector 是不是很简单”，你如何承认局限并说明价值？

## Day 9：ReActAgent 和 AgentToolkit

**目标：** 吃透原生 ReAct 的 Thought-Action-Observation 循环。

**阅读：**

- `sql_agent/agent/react_agent.py`
- `sql_agent/agent/tools.py`
- `tests/test_agent_tools.py`

**命令：**

```bash
pytest -q tests/test_agent_tools.py
```

**必须理解：**

- ReActAgent 如何构造 system prompt。
- LLM 如何通过工具描述知道有哪些工具。
- `_parse_react_step()` 如何解析 Thought/Action/Action Input。
- 工具执行后的 Observation 如何回填给 LLM。
- `AgentToolkit` 中每个工具的用途。
- 工具层 schema 白名单校验如何降低风险。

**当日产出：**

- 画 ReAct 执行循环图。
- 写一段模拟轨迹：Question -> Thought -> Action -> Observation -> Final SQL。

**自测问题：**

- 为什么不能让 LLM 直接拼 SQL 后执行？
- `DbTablesWithRelevanceScores` 如何找相关表？
- `DbColumnEntityChecker` 为什么重要？
- ReAct system prompt 中为什么要列出所有工具？
- 为什么提示词要求先找相关表，再取 schema？
- 为什么时间类问题要先调用 `SystemTime`？
- `_parse_react_step()` 用正则解析有什么风险？
- 如果 LLM 输出未知工具名，系统如何处理？
- Observation 太长为什么要截断？
- 工具执行异常为什么要转成 Observation 返回给 LLM？
- `SqlDbQuery` 执行前为什么要清理 markdown 代码块？
- embedding 相似度为什么用 cosine similarity？
- 如果 LLMBackend.embed 返回维度不一致，会发生什么？
- `DbRelevantTablesSchema` 如何匹配带 schema 和不带 schema 的表名？
- `DbRelevantColumnsInfo` 为什么要展示 sample values？
- `DbColumnEntityChecker` 中 exact match 和 fuzzy match 分别解决什么问题？
- 工具层白名单如何防止 LLM 伪造表名？
- few-shot 工具为什么不是永远可用，而是有样例才加入？
- 管理员指令为什么要标注 MUST follow？
- Agent 工具越多越好吗？有什么代价？
- ReAct 循环为什么需要最大迭代次数？
- 如果 ReAct 达到最大迭代次数，fallback final generation 有什么风险？
- 面试官问“你怎么调试 Agent 错误”，你会看哪些 steps？

## Day 10：PlanSolveAgent 和复杂查询规划

**目标：** 掌握复杂 SQL 的先规划再执行范式。

**阅读：**

- `sql_agent/agent/plan_solve_agent.py`
- `sql_agent/agent/react_agent.py`

**命令：**

```bash
pytest -q tests/test_agent_base.py tests/test_complex_sql.py
```

**必须理解：**

- PlanSolveAgent 比 ReAct 多了 plan phase。
- 计划阶段要识别表、JOIN、过滤、聚合、排序。
- 执行阶段仍然通过 AgentToolkit 使用工具。
- 达到最大迭代次数后会 fallback 到 final SQL prompt。

**当日产出：**

- 写一个复杂业务问题的完整 SQL 生成计划。
- 写 ReAct vs Plan-and-Solve 对比表。

**自测问题：**

- 哪些问题不适合 Plan-and-Solve？
- 为什么复杂查询先规划更稳？
- fallback 机制有什么价值？
- Plan phase 的 prompt 要求输出哪些结构化信息？
- PlanSolveAgent 如何把 table list 提供给 LLM？
- 计划阶段是否真的执行工具？和执行阶段有什么区别？
- PlanSolveAgent 的第一步 `StepResult` 为什么记录 Plan？
- Execute phase 如何复用 AgentToolkit？
- PlanSolveAgent 解析 Action 的逻辑和 ReActAgent 有什么不同？
- 如果计划本身错了，后续执行会怎样？
- 如何用执行反馈修正错误计划？
- 复杂 SQL 中 JOIN、WHERE、GROUP BY、ORDER BY 的顺序如何理解？
- 排名类问题通常需要 `ORDER BY` 还是窗口函数？
- “每个部门销售额最高的员工”为什么比“销售额最高的员工”复杂？
- 什么时候应该使用 CTE？
- 什么时候应该使用子查询？
- 什么时候应该使用窗口函数？
- Plan-and-Solve 会不会比 ReAct 更慢？为什么？
- 如何用 AgentSelector 控制成本和质量之间的平衡？
- 如果用户强制 simple 问题走 PlanSolve，会有什么浪费？
- 面试官问“Plan-and-Solve 和 Chain-of-Thought 有什么关系”，你如何回答？
- 复杂查询规划中最容易漏掉哪类条件？
- 你如何验证 PlanSolveAgent 生成的 SQL 真正回答了问题？

## Day 11：Context、Few-shot、Conversation

**目标：** 理解上下文如何影响 SQL 生成。

**阅读：**

- `sql_agent/context/conversation.py`
- `sql_agent/context/retriever.py`
- `sql_agent/context/base.py`
- `tests/test_conversation.py`
- `tests/test_api_e2e.py`

**命令：**

```bash
pytest -q tests/test_conversation.py tests/test_api_e2e.py
```

**必须理解：**

- `ConversationManager` 如何创建、更新、截断和删除会话。
- `ContextRetriever` 如何检索 Golden SQL 和管理员指令。
- `DefaultContextStore` 如何组合 vector store 和 storage。
- 多轮历史如何注入 Agent prompt。

**当日产出：**

- 画“上下文注入流程图”。
- 写 3 组多轮问答样例，每组包含上一轮 SQL 和下一轮追问。

**自测问题：**

- Prompt 和 Conversation 的关系是什么？
- Few-shot 示例如何影响 SQL 风格和表选择？
- 多轮对话在 NL->SQL 中最容易出什么错？
- `ConversationManager.create_conversation()` 创建了哪些字段？
- `get_or_create()` 如何处理不存在的 conversation_id？
- 会话 TTL 的作用是什么？
- `add_turn()` 为什么要在添加后做截断？
- `max_turns` 和 `max_tokens` 分别想控制什么？
- 当前 token 控制是否真正按 token 计算？有什么改进空间？
- `build_context_prompt()` 如何组织历史轮次？
- 为什么只取最近几轮，而不是所有历史？
- 多轮追问中的指代消解有哪些例子？
- 如果上一轮 SQL 错了，下一轮引用它会有什么风险？
- `ContextRetriever.retrieve_few_shot_examples()` 如何通过 vector store 找样例？
- 为什么检索到 id 后还要去 storage 取完整 Golden SQL？
- 管理员指令按 db_connection_id 过滤有什么意义？
- Golden SQL 和 Instruction 在 prompt 中优先级如何理解？
- 如果 few-shot 示例和当前 schema 不一致，会有什么问题？
- 如何评估 few-shot 召回质量？
- 为什么端到端测试要验证 conversation history？
- 如果多用户共享内存 conversation，会有什么安全风险？
- 生产环境 conversation 应该存在哪里？
- 面试官问“如何处理用户说‘那上个月呢’”，你怎么回答？

## Day 12：自纠错、评估和 benchmark

**目标：** 掌握 SQL 生成后的验证、执行反馈和质量评估。

**阅读：**

- `sql_agent/correction/base.py`
- `sql_agent/correction/din_style.py`
- `sql_agent/correction/dail_style.py`
- `sql_agent/eval/evaluator.py`
- `sql_agent/eval/harness.py`
- `sql_agent/eval/run_api_cases.py`
- `tests/test_correction.py`
- `tests/test_evaluator.py`
- `tests/test_eval_harness.py`
- `tests/test_eval_benchmark_2.py`
- `tests/test_business_benchmark_dataset.py`

**命令：**

```bash
pytest -q tests/test_correction.py tests/test_evaluator.py tests/test_eval_harness.py tests/test_eval_benchmark_2.py tests/test_business_benchmark_dataset.py
```

**必须理解：**

- `SQLCorrector.validate_sql()` 如何验证 SQL。
- DIN-SQL 风格是 verify-then-fix。
- DAIL-SQL 风格是 execute-feedback-fix。
- SQL 可执行不等于语义正确。
- Evaluation Benchmark 2.0 如何输出 tag metrics 和 error breakdown。
- API case runner 如何批量调用 `/api/v1/question` 并生成 Markdown 报告。
- SQLite business benchmark 如何验证原型链路。

**当日产出：**

- 画“SQL 自纠错闭环图”。
- 写 DIN vs DAIL 对比表。

**自测问题：**

- 执行成功但返回 0 行是否一定正确？
- LLM 评估和启发式评估分别有什么局限？
- 自纠错可能引入什么新风险？
- `SQLCorrector` 为什么设计成抽象基类？
- `validate_sql()` 在 PostgreSQL 和其他数据库上的验证方式有什么不同？
- `SELECT * FROM (sql) AS _sub LIMIT 0` 验证的是什么？
- 这种验证能发现语义错误吗？
- DINStyleCorrector 的 prompt 分几步？
- DIN 中 `VERIFIED: true` 有什么作用？
- 如果 LLM 错误地说 VERIFIED true，会有什么风险？
- DAILStyleCorrector 为什么先执行 SQL？
- `_execute_and_get_feedback()` 会返回哪些信息？
- 为什么样本结果也可以作为反馈？
- 为什么 row_count 为 0 时只警告，不直接判定失败？
- consistency check prompt 解决什么问题？
- 自纠错最大轮数为什么不能无限大？
- 自纠错会增加哪些成本？
- SQL 修正前后如何保留审计信息？
- `SimpleEvaluator.evaluate()` 的启发式规则有哪些？
- LLM evaluator 为什么可能不稳定？
- `EvaluationHarness` 如何计算 valid rate、execution accuracy、grounding rate？
- `error_breakdown` 如何帮助定位回归？
- API benchmark runner 为什么要和模块级 harness 分开？
- 为什么原型阶段不保留外部服务集成测试？
- 如何解释 MockLLM + SQLite benchmark 的测试价值？
- 面试官问“如何评估 NL->SQL 准确率”，你会提出哪些指标？

## Day 13：Semantic / Ranking / Analysis / Visualization 2.0

**目标：** 吃透项目当前最能体现“从 demo 到系统”的 2.0 能力。

**阅读：**

- `sql_agent/semantic/types.py`
- `sql_agent/semantic/planner.py`
- `sql_agent/semantic/compiler.py`
- `sql_agent/ranking/ranker.py`
- `sql_agent/analysis/result_analyzer.py`
- `sql_agent/visualization/recommender.py`
- `tests/test_semantic_layer_2.py`
- `tests/test_candidate_ranking_2.py`
- `tests/test_result_analysis_2.py`
- `tests/test_visualization_2.py`

**命令：**

```bash
pytest -q tests/test_semantic_layer_2.py tests/test_candidate_ranking_2.py tests/test_result_analysis_2.py tests/test_visualization_2.py
```

**必须理解：**

- Semantic Layer 2.0 如何表达指标治理、时间粒度、多指标、Join 和歧义澄清。
- CandidateRanker 2.0 如何输出 `score_breakdown`、`selection_reason`、`source` 和 `result_shape`。
- ResultAnalyzer 2.0 如何生成 Top K、占比、比较和 why limitation。
- Visualization 2.0 如何输出 ECharts option，并做字段校验。

**当日产出：**

- 画“SemanticQueryPlan -> CandidateRanker -> ResultAnalyzer -> Visualization”链路图。
- 写一段 3 分钟口述稿：为什么这个项目不是简单 Text-to-SQL demo。

**自测问题：**

- 为什么指标要有 owner、version 和 certified？
- 为什么 SQL 应该是 SemanticQueryPlan 的编译产物？
- 多指标查询和歧义查询分别如何表达？
- relationship Join 编译目前支持到什么程度？
- 为什么 CandidateRanker 要校验结果形状？
- count、group-by、trend 三类问题的结果形状分别是什么？
- verified query bonus 是否意味着可以跳过执行？为什么不能？
- `score_breakdown` 和 `selection_reason` 面试时怎么讲？
- ResultAnalyzer 为什么要区分 finding type？
- 为什么 why 类问题不能直接给原因？
- 占比 finding 的 evidence 如何写才 grounded？
- ECharts option 和轻量 spec 各有什么价值？
- line chart 为什么要求 x 是时间字段？
- pie chart 为什么只用于占比或份额场景？
- 这些 2.0 能力如何帮助项目从 demo 变系统？

## Day 14：端到端复盘、模拟面试和最终答辩材料

**目标：** 把所有模块串成完整系统，并形成可直接用于秋招面试的表达材料。

**阅读：**

- `tests/test_api_e2e.py`
- `tests/fakes.py`
- `sql_agent/api/routes.py`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
- `docs/iterations/2026-08-13-230519-data-agent-2-0-deepening.md`

**命令：**

```bash
pytest -q tests/test_api_e2e.py tests/test_ioc_registry.py
pytest -q tests
```

**必须完成：**

- 写“项目缺陷与改进方向清单”。
- 画“测试金字塔”。
- 5 分钟项目介绍稿。
- 15 分钟深挖版讲解提纲。
- 20 个面试追问与答案。
- 核心技术细节速查表。
- 项目不足与改进路线。
- 最终测试结果记录：以当前 `pytest -q tests` 输出为准。

**验收标准：**

- 能在 5 分钟内讲清项目背景、架构、亮点、难点和不足。
- 能白板画主链路、ReAct 循环、Schema Linking、自纠错闭环、SemanticQueryPlan、CandidateRanker、ResultAnalyzer grounding 和 Evaluation Benchmark。
- 能回答至少 80% 高频追问，不依赖 README。

**自测问题：**

- 用 30 秒介绍这个项目，你怎么说？
- 用 2 分钟介绍这个项目，你怎么说？
- 用 5 分钟介绍这个项目，你怎么说？
- 如果面试官只允许你讲一个技术亮点，你讲哪个？为什么？
- 如果面试官问“这个项目难点在哪里”，你按哪三点回答？
- 如果面试官问“你做了哪些工作”，你如何区分分析、重构、测试、文档？
- 如果面试官质疑“这只是调用外部模型”，你如何反驳？
- 如果面试官质疑“规则很简单”，你如何承认局限并说明工程价值？
- 如果面试官问“为什么不用 LangChain”，你如何回答？
- 如果面试官问“为什么不用 RAG 直接回答”，你如何解释 NL->SQL 的特殊性？
- 如果面试官让你现场画架构图，你先画哪些模块？
- 如果面试官让你现场写一个 SQL 示例，你选哪个业务场景？
- 如果面试官让你解释测试，如何从单元测试讲到端到端测试？
- 如果面试官问当前测试结果说明什么，你怎么解释？
- 如果面试官问为什么不做外部服务集成测试，你如何回答？
- 如果面试官让你设计生产部署，你会补哪些组件？
- 如果面试官问“如何做权限控制”，你怎么回答？
- 如果面试官问“如何防止数据泄露”，你怎么回答？
- 如果面试官问“如何评估 SQL 语义正确性”，你怎么回答？
- 如果面试官问“如何处理 schema 特别大”，你怎么回答？
- 如果面试官问“如何降低延迟”，你怎么回答？
- 如果面试官问“如何降低 token 成本”，你怎么回答？
- 如果面试官问“如何处理多轮对话错误累积”，你怎么回答？
- 如果面试官问“如何处理外键缺失”，你怎么回答？
- 如果面试官问“如果继续做三个月会做什么”，你怎么规划？
- 如果面试官问“这个项目最失败的设计是什么”，你准备怎么答？
- 如果面试官问“你从 Dataherald 学到了什么”，你怎么答？
- 如果面试官问“这个项目体现了你的哪些工程能力”，你怎么答？

## 每日测试计划

```text
Day 1 / Day 14:
pytest -q tests

Day 5:
pytest -q tests/test_sql_database.py tests/test_integration.py

Day 6:
pytest -q tests/test_schema_scanner_samples.py

Day 7:
pytest -q tests/test_schema_linking.py tests/test_complex_sql.py

Day 8:
pytest -q tests/test_agent_base.py

Day 9:
pytest -q tests/test_agent_tools.py

Day 11:
pytest -q tests/test_conversation.py tests/test_api_e2e.py

Day 12:
pytest -q tests/test_correction.py tests/test_evaluator.py tests/test_eval_harness.py tests/test_eval_benchmark_2.py tests/test_business_benchmark_dataset.py

Day 13:
pytest -q tests/test_semantic_layer_2.py tests/test_candidate_ranking_2.py tests/test_result_analysis_2.py tests/test_visualization_2.py
```
