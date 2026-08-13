# 2026-07-15 23:41:20 SQL Agent 后端补齐迭代记录

> 历史记录说明：本文记录的是后端基础补齐当次迭代状态。当前项目已经继续扩展到 Semantic Layer 2.0、CandidateRanker 2.0、ResultAnalyzer 2.0、Visualization 2.0 和 Evaluation Benchmark 2.0，最新状态见 `README.md` 与 `docs/iterations/2026-08-13-230519-data-agent-2-0-deepening.md`。

## 本次目标

围绕 README 后续开发计划，补齐 SQL Agent 在依赖实例化、真实数据库连接加载、跨请求多轮会话、SQL 提取、工具安全校验、Schema 扫描上下文和集成测试方面的缺口。

## 已完成内容

1. IoC 注册表补齐
   - `System.instance()` 现在支持通过环境变量自动实例化：
     - `LLMBackend`
     - `StorageBackend`
     - `VectorBackend`
     - `ContextStore`
     - `Evaluator`
   - 增加实现类继承关系校验，避免环境变量指向错误类型时静默失败。

2. `/api/v1/question` 真实连接加载
   - API 现在从 `db_connections` 存储集合读取 `DatabaseConnection`。
   - 未找到连接时返回 `404 Database connection not found`。
   - 不再使用空 `connection_uri` 创建 SQLAlchemy engine。

3. 跨请求多轮会话
   - API 级 `System` 改为进程内单例，避免每个请求重新创建存储和向量组件。
   - `ConversationManager` 增加可选存储后端，会将会话写入 `conversations` 集合。
   - `/api/v1/conversations` 和删除接口改为读取存储化会话。

4. `extract_sql_from_output()` 修复
   - 跳过异常 markdown 中的空 SQL 代码块。
   - 支持普通 fenced code block。
   - 对没有有效代码块但包含 `SELECT` 或 `WITH` 的输出提供后备提取。

5. SQLite + MockLLM API 端到端测试
   - 新增 `tests/test_api_e2e.py`。
   - 使用临时 SQLite 文件、FastAPI TestClient、内存存储、内存向量库和 MockLLM。
   - 覆盖：
     - 创建数据库连接。
     - `/api/v1/question` 从存储加载连接。
     - 返回 MockLLM SQL。
     - 同一 `conversation_id` 跨请求复用。
     - 缺失连接返回 404。

6. 工具层 schema 白名单校验
   - `DbRelevantTablesSchema`、`DbRelevantColumnsInfo`、`DbColumnEntityChecker` 均会校验表名和列名是否来自扫描结果。
   - `SqlDbQuery` 在执行前校验 SQL 中出现的表名，单表查询时额外校验简单列名。
   - 当运行环境缺少 `sql_metadata` 时，会降级到正则后备解析，不阻断模块测试。

7. SchemaScanner 样本值和列级上下文
   - 修复 SQLAlchemy 2 下裸字符串执行导致采样失败的问题。
   - 为列元数据写入：
     - `sample_values`
     - `categories`
     - `low_cardinality`
   - `table_schema` 中追加列样本注释，便于 Agent 获取列级上下文。
   - 写入 `row_count`。

8. 真实外部集成测试
   - 新增 `tests/test_real_integrations.py`。
   - 默认跳过，避免普通测试访问外部服务。
   - 设置 `RUN_REAL_INTEGRATIONS=true` 后可测试：
     - 真实 OpenAI 生成与 embedding。
     - 真实 MongoDB 存储读写删除。
     - 真实 ChromaDB 向量写入和查询。

9. 代码清理
   - 移除 API 中旧的未使用 `_conversations` 全局字典。
   - 清理本轮涉及文件中的未使用导入。
   - 修复 `SimpleEvaluator` 与 `Evaluator` 的继承契约。
   - 修复 `ReActAgent`、`PlanSolveAgent` 的 `stream_sql()` 签名，使其和抽象基类一致。

## 测试结果

模块测试命令：

```powershell
pytest tests -q
```

结果：

```text
81 passed, 3 skipped, 2 warnings
```

说明：

- 3 个 skipped 是真实 OpenAI、MongoDB、ChromaDB 集成测试，默认需要 `RUN_REAL_INTEGRATIONS=true` 才运行。
- warnings 来自：
  - FastAPI TestClient 对当前 httpx/starlette 组合的弃用提示。
  - `.pytest_cache` 在当前工作区权限下无法写入 nodeids 的提示。

全仓库测试命令：

```powershell
pytest -q
```

结果：

```text
services/engine/dataherald/tests 收集阶段失败：ModuleNotFoundError: No module named 'sql_metadata'
```

分析：

- 失败发生在参考子项目 `services/engine/dataherald` 的测试收集阶段，不属于本轮 `sql_agent` 模块范围。
- 当前运行环境未安装该子项目测试所需依赖 `sql_metadata`。
- 本轮目标模块通过 `pytest tests -q` 已完成验证。

## 效果分析

1. API 链路从“可演示”推进到“可真实使用”
   - `/question` 不再依赖空连接占位符，能够基于已登记连接扫描 schema 并生成 SQL。
   - SQLite + MockLLM 端到端测试证明主链路可以不依赖真实 LLM 完成稳定回归。

2. 多轮会话从请求内存升级为可恢复状态
   - 旧实现每次请求都创建新的 `ConversationManager`，导致同一 `conversation_id` 不能跨请求保留历史。
   - 新实现将会话写入存储，后续可以自然替换为 MongoDB 持久化。

3. 工具层安全边界更明确
   - LLM 传入工具的表名、列名必须来自扫描得到的 schema。
   - 这可以降低幻觉表名、幻觉列名和越权查询的风险。
   - 当前 SQL 解析对复杂多表列级校验仍保持保守策略，优先阻断未知表，避免误杀复杂合法 SQL。

4. Schema 上下文对生成质量更友好
   - 列样本值、低基数分类值和行数能帮助 Agent 判断实体值、过滤条件和枚举列。
   - 这对“某个部门/分类/状态”的自然语言问题尤其重要。

## 剩余风险与后续建议

1. 真实外部服务测试未在本次环境中执行
   - 原因：默认不访问外部服务，且未确认真实 `OPENAI_API_KEY`、`MONGODB_URI` 等凭据。
   - 建议在 CI 或本地受控环境中执行：

```powershell
$env:RUN_REAL_INTEGRATIONS="true"
$env:OPENAI_API_KEY="..."
$env:MONGODB_URI="..."
pytest tests/test_real_integrations.py -q
```

2. `SqlDbQuery` 的复杂 SQL 列级校验仍可加强
   - 当前对多表查询主要校验表名，避免 alias、聚合、表达式导致大量误判。
   - 后续可引入稳定 SQL AST 解析器，建立 alias 到表的映射后再做严格列校验。

3. MongoDB 会话序列化已按普通 dict/datetime 处理
   - 当前结构适配 PyMongo 基础写入。
   - 若后续引入 Pydantic 或复杂类型，需要统一存储序列化策略。

4. 全仓库测试仍受参考子项目依赖影响
   - 若希望一条命令覆盖所有子项目，需要为 `services/engine` 单独安装依赖，或配置 pytest 默认只收集主工程测试。
