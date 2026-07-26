# SQL Agent 面试答辩手册

## 1. 五分钟项目介绍稿

我这个项目是基于开源 NL->SQL 项目 Dataherald 的架构分析后做的一版核心引擎重构。Dataherald 原始项目是一个企业级自然语言转 SQL 平台，包含 Engine、Enterprise、Admin Console、Slackbot 等服务，核心链路依赖 FastAPI、LangChain、OpenAI、MongoDB 和 ChromaDB。

我重点关注的是它的核心 Engine，也就是用户输入自然语言问题后，系统如何理解数据库 schema、检索上下文、调用 Agent 工具、生成 SQL 并做验证。分析后我发现原始架构里几个值得增强的点：一是 Agent 控制流依赖 LangChain ZeroShotAgent，可控性有限；二是多轮对话能力不强；三是复杂 SQL，尤其是多表 JOIN 和聚合查询容易出错；四是生成后主要做语法验证，缺少执行反馈驱动的自纠错闭环。

因此我抽取核心链路，重构了一个轻量级 SQL Agent 原型。整体链路是：FastAPI 接收问题，构造 Prompt 和 Conversation；SchemaScanner 扫描数据库表、列、主键、外键和样本值；ContextRetriever 检索 Golden SQL few-shot 示例和管理员指令；AgentSelector 根据问题复杂度选择 ReActAgent 或 PlanSolveAgent；Agent 通过 AgentToolkit 调用查表、取 schema、检查实体值、执行 SQL 等工具；生成 SQL 后再进入 DAIL 或 DIN 风格自纠错，最终返回 SQL 和中间步骤。

项目里我比较重视可替换架构，所以实现了一个 IoC 容器，LLM、存储、向量库、上下文和评估器都通过接口注入。这样后续把 OpenAI 换成本地模型，或者把 ChromaDB 换成其他向量库，不需要改业务主链路。

测试方面，我用 pytest 做了分层测试：底层有数据模型、SQL 执行、schema 扫描、schema linking 测试；中间有 Agent 工具和自纠错测试；上层有 API 端到端测试，并用 fake storage、fake vector store 和 mock LLM 隔离真实外部依赖。当前 `pytest -q tests` 是 81 passed、3 skipped，skip 主要是依赖真实 OpenAI、MongoDB、ChromaDB 环境的集成测试。

这个项目目前定位是核心 Agent 引擎重构原型，不是完整生产平台。后续如果继续做，我会优先补充权限和审计、schema 大规模压缩、真实评测集、Langfuse 链路追踪和更严格的 SQL AST 安全校验。

## 2. 十五分钟深挖讲解提纲

1. 背景：Dataherald 是什么，原始架构如何拆分。
2. 问题：LangChain Agent 可控性、多轮上下文、复杂 JOIN、自纠错不足。
3. 总体架构：API -> Context -> Schema -> Agent -> Tools -> Correction。
4. 数据模型：Prompt、Conversation、TableDescription、SQLGeneration。
5. IoC：System.instance 如何替换 LLM、Storage、VectorStore。
6. SchemaScanner：如何扫描主键、外键、样本值、低基数字段。
7. SchemaLinker：外键图、JOIN 路径、BFS。
8. ReActAgent：Thought-Action-Observation。
9. PlanSolveAgent：Plan phase 和 Execute phase。
10. AgentToolkit：工具列表、schema 白名单、执行验证。
11. Context：Golden SQL、管理员指令、多轮历史。
12. Correction：DIN 语义验证、DAIL 执行反馈。
13. Testing：fake 组件、端到端测试、真实集成 skip。
14. 风险：SQL 安全、LLM 幻觉、schema 过大、外键缺失。
15. 后续：观测、评测、安全、模型适配。

## 3. 高频追问与参考答案

### Q1：为什么要参考 Dataherald？

Dataherald 是一个比较完整的开源 NL->SQL 项目，包含核心引擎、企业层、管理后台和 Slackbot，能代表企业级数据问答系统的常见架构。我参考它是为了从真实项目中抽取核心链路，而不是凭空设计一个 toy demo。

### Q2：你的项目和 Dataherald 最大区别是什么？

最大区别是我把核心 Engine 做了轻量化和 Agent 化重构。原始 Dataherald 更依赖 LangChain ZeroShotAgent，我这里实现了原生 ReActAgent 和 PlanSolveAgent，并加入多轮上下文、Schema Linking 和执行反馈自纠错。

### Q3：为什么不直接用 LangChain Agent？

LangChain 能快速搭建，但对底层 Thought-Action-Observation 循环、工具执行、错误处理和中间步骤控制不够透明。这个项目的目标是学习和验证 NL->SQL Agent 的核心机制，所以我选择自己实现 Agent 控制流，便于调试、测试和面试解释。

### Q4：ReAct 和 Plan-and-Solve 怎么选？

项目用 `AgentSelector` 根据问题复杂度选择。简单或中等问题走 ReAct，复杂问题，比如多表 JOIN、聚合、排名、同比环比等，走 Plan-and-Solve。ReAct 更轻量，Plan-and-Solve 更适合需要先拆解再执行的复杂 SQL。

### Q5：ReAct 的核心流程是什么？

ReAct 是 Thought-Action-Observation 循环。LLM 先分析当前问题，选择工具，系统执行工具并返回观察结果，LLM 再基于观察继续推理，直到输出最终 SQL。

### Q6：PlanSolveAgent 比 ReAct 多了什么？

多了一个显式计划阶段。它会先识别需要哪些表、JOIN 条件、过滤条件、聚合方式和排序逻辑，再进入工具执行阶段。这样能降低复杂查询中一步到位生成 SQL 的错误率。

### Q7：Schema Linking 是怎么做的？

`SchemaLinker` 遍历 `TableDescription` 中的外键信息，构建表关系图。每个表是节点，外键是边。多表查询时，可以根据目标表集合找到 JOIN 条件，也可以用 BFS 查两个表之间的连接路径。

### Q8：如果数据库没有外键怎么办？

这是当前方案的限制。可以退化到表名、列名、样本值和历史 Golden SQL 的启发式匹配。生产级系统里还应支持人工配置业务关系，或者从历史 SQL 中挖掘隐式 JOIN 关系。

### Q9：为什么要做 SchemaScanner？

LLM 本身不知道数据库有哪些表和列。如果直接让它生成 SQL，很容易幻觉出不存在的列。SchemaScanner 把真实数据库结构转换成 `TableDescription`，为 Agent 提供可信 schema 上下文。

### Q10：样本值有什么用？

样本值能帮助实体匹配。例如用户说“Engineering 部门”，系统可以通过列样本知道这个值存在于 `departments.name`。这比只看列名更准确。

### Q11：如何防止 LLM 生成危险 SQL？

当前有几层防线：`SQLDatabase` 会拦截 `DROP`、`DELETE`、`UPDATE` 等危险命令；工具层对表名和列名做 schema 白名单校验；生产环境还应该使用只读数据库账号、SQL AST 解析、查询超时、行数限制和审计日志。

### Q12：SQL 可执行就一定正确吗？

不一定。SQL 可执行只能说明语法和表列大概率没问题，但可能语义错误，比如聚合维度错、过滤条件错、JOIN 类型错。因此项目里除了 DAIL 执行反馈，也有 DIN 风格的语义验证思路。

### Q13：DAIL-SQL 风格自纠错是什么？

它的核心是 execute-feedback-fix。先执行 SQL，拿到数据库错误或样本结果，再把反馈交给 LLM 生成修正版 SQL，循环直到通过或达到最大轮数。

### Q14：DIN-SQL 风格自纠错是什么？

它更偏 verify-then-fix。先判断 SQL 是否回答了问题，如果不正确，再定位具体错误，比如表列错误、JOIN 错误、过滤条件错误、聚合错误，然后生成修正版。

### Q15：为什么端到端测试要用 MockLLM？

真实 LLM 不稳定、成本高、速度慢，而且输出不确定。端到端测试的目标是验证系统链路，不是验证 OpenAI 能力，所以用 MockLLM 可以稳定触发预期路径。

### Q16：真实集成测试为什么会 skip？

OpenAI、MongoDB、ChromaDB 依赖本地环境变量和外部服务。没有配置时跳过是合理的，否则 CI 或本地开发会因为缺外部环境而失败。

### Q17：如果 schema 有 1000 张表怎么办？

不能把所有 schema 都塞进 prompt。需要分层检索：先用 embedding 或关键词召回相关表，再取这些表的列信息和 JOIN 邻居；还可以做 schema 摘要、列级压缩和缓存。

### Q18：如果线上延迟很高怎么优化？

可以缓存 schema 扫描结果、缓存 embedding、减少工具调用轮数、限制 PlanSolve 使用场景、并行获取上下文、使用更快模型、对常见问题走 Golden SQL 命中或模板化查询。

### Q19：这个项目目前离生产级还差什么？

还需要更严格的权限控制、审计日志、SQL AST 安全校验、大规模 schema 管理、稳定的评测集、线上观测、成本控制、租户隔离、连接凭证加密和完整部署方案。

### Q20：如果继续做一个月，你优先做什么？

我会优先做三件事：第一，接入 Langfuse 或类似工具记录 Agent 推理链路；第二，引入标准 NL->SQL 评测集和项目自己的 Golden SQL 集；第三，加强 SQL 安全，包括只读连接、AST 解析、白名单和审计。

## 4. 项目不足的高质量回答模板

这个项目目前是核心引擎重构原型，不是完整生产平台。我认为主要不足有三类：

第一是安全和权限还不够生产级。虽然有危险 SQL 拦截和 schema 白名单，但更稳妥的方式应该是只读账号、AST 级 SQL 校验、查询超时、行数限制和审计日志。

第二是大规模 schema 场景还需要优化。当前方案适合中小规模 schema，如果数据库有上千张表，就需要 schema 分层检索、摘要压缩、缓存和业务关系配置。

第三是评测和观测还需要加强。当前测试能覆盖核心模块和端到端链路，但真实 SQL 语义正确性需要结合 Golden SQL 数据集、执行准确率指标和 Agent 推理链路追踪。

这样的不足不影响项目作为学习和验证核心架构的价值，但如果走向生产，这些是我会优先补齐的方向。
