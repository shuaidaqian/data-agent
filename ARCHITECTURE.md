 # Dataherald 项目架构深度分析
 
 > 分析日期: 2026-07-05
 > 基于: [Dataherald/dataherald](https://github.com/Dataherald/dataherald) — Apache 2.0 开源 NL→SQL 引擎
 
 ---
 
 ## 一、项目概览
 
 Dataherald 是一个 **自然语言转 SQL 引擎**，面向企业级的问答场景。它能让你用自然语言直接查询关系型数据库。核心引擎基于 Python FastAPI + LangChain，管理后台基于 Next.js。
 
 - **许可证:** Apache 2.0
- **核心依赖:** LangChain、外部 LLM、向量库、文档库
 - **项目形态:** Monorepo — services/ 下四个子服务
 
 | 服务 | 技术栈 | 职责 |
 |------|--------|------|
 | Engine (services/engine/) | Python FastAPI, LangChain | 核心 NL→SQL 引擎 |
 | Enterprise (services/enterprise/) | Python FastAPI | 认证、组织、用户、计费、API Key |
 | Admin-console (services/admin-console/) | Next.js, React | 管理控制台 UI |
 | Slackbot (services/slackbot/) | Node.js | Slack 机器人集成 |
 
 ---
 
 ## 二、整体架构
 
 Dataherald 采用四服务部署架构：
 
 - **Engine** 是核心 NL→SQL 引擎，对外暴露 REST API
 - **Enterprise** 是 API 网关层，叠加认证、组织、计费等业务逻辑
 - **Admin-console** 是 Next.js 前端，提供配置和监控 GUI
 - **Slackbot** 是 Slack 频道内的交互机器人
 
 ---
 
 ## 三、Engine 核心架构
 
 ### 3.1 插件化依赖注入（IoC 容器）
 
 config.py 定义了可插拔接口系统，所有核心组件可通过环境变量替换：
 
     api_impl       = "dataherald.api.fastapi.FastAPI"
     db_impl        = "dataherald.db.<document-store>"
     db_scanner_impl= "dataherald.db_scanner.sqlalchemy.SqlAlchemyScanner"
     eval_impl      = "dataherald.eval.simple_evaluator.SimpleEvaluator"
     context_store_impl = "dataherald.context_store.default.DefaultContextStore"
     vector_store_impl  = "dataherald.vector_store.<vector-store>"
 
 System 类通过 instance() 方法懒加载组件实例，实现依赖注入。
 
 ### 3.2 核心数据流
 
 NL→SQL 的完整旅程：
 
 1. 用户提问 → API 创建 Prompt
 2. SQLGenerationService 调用 SQL Agent
 3. Agent 从 ContextStore 获取 few-shot 示例和管理员指令
 4. Agent 使用 ReAct 框架自动选择工具：检索相关表、获取 Schema、检查列值、执行试运行
 5. LLM 生成 SQL → 语法验证 → 返回 SQLGeneration 对象
 6. 可选：执行 SQL + 生成自然语言回答（NLGeneration）
 
 ### 3.3 SQL Agent 工具链
 
 基于 LangChain ZeroShotAgent（ReAct 框架），包含 8 个工具：
 
 | 工具名称 | 类名 | 用途 |
 |----------|------|------|
 | FewshotExamplesRetriever | GetFewShotExamples | 从向量库检索相似问-SQL 对 |
 | DbTablesWithRelevanceScores | TablesSQLDatabaseTool | Embedding 找 top-20 相关表 |
 | DbRelevantTablesSchema | SchemaSQLDatabaseTool | 获取指定表的完整 Schema |
 | DbRelevantColumnsInfo | InfoRelevantColumns | 获取列的描述、类别、样本值 |
 | DbColumnEntityChecker | ColumnEntityChecker | 检查列中是否有匹配的实体值 |
 | SqlDbQuery | QuerySQLDataBaseTool | 执行 SQL 查询 |
 | GetAdminInstructions | GetUserInstructions | 获取管理员指令 |
 | SystemTime | SystemTime | 获取当前时间 |
 
 ### 3.4 提示策略选择
 
 Agent 根据 few-shot 和 instruction 的有无自动选择四种 Plan 策略。
 
 ### 3.5 数据库扫描器
 
 支持多数据源 Schema 自动发现：PostgreSQL、BigQuery、Snowflake、ClickHouse、Redshift、SQL Server、Databricks。
 
 ### 3.6 上下文检索
 
 DefaultContextStore 实现两类上下文注入：向量相似度检索 GoldenSQL，以及匹配当前连接的管理员指令。向量库实现可按部署环境替换。
 
 ### 3.7 核心数据模型
 
 - Prompt: 用户提问，包含 text, db_connection_id, schemas
 - SQLGeneration: SQL 生成结果，包含 prompt_id, sql, status, tokens_used, confidence_score
 - NLGeneration: 自然语言回答，包含 sql_generation_id, text
 - GoldenSQL: 黄金示例，包含 prompt_text, sql, db_connection_id
 - Instruction: 管理员指令
 - Finetuning: 微调任务
 
 ---
 
 ## 四、关键改进方向
 
 ### 4.1 Agent 模式升级
 
 - 现状：依赖 LangChain 的 ZeroShotAgent，执行器较为简单
 - 改进方向：实现原生 ReAct Agent（更可控的 T-A-O 循环），实现 Plan-and-Solve Agent（先规划再执行），支持根据问题复杂度自动选择 Agent 模式
 
 ### 4.2 多轮对话上下文管理
 
 - 现状：每次提问完全独立，无历史上下文
 - 改进方向：ConversationManager 维护对话历史，引用消歧（"上个月" → 根据历史推断），上下文窗口管理（Token 预算控制）
 
 ### 4.3 复杂 SQL 处理
 
 - 现状：对多表 JOIN、嵌套子查询、CTE 支持较弱
 - 改进方向：Schema Linking 增强（精确识别 JOIN 路径），复杂查询分解器，SQL 骨架匹配
 
 ### 4.4 Self-Correct 机制
 
 - 现状：生成后仅做语法验证
 - 改进方向：DIN-SQL 风格分阶段流水线，DAIL-SQL 风格执行反馈驱动迭代修正，交叉验证一致性检查
 
 ---
 
 *本文档基于对 Dataherald 项目源代码的完整分析编写。*
