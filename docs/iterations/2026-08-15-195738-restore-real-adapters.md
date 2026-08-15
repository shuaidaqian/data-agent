# 2026-08-15 19:57:38 Restore Real Adapter Integration Paths

## 本次目标

本次迭代针对上一轮“本地原型化清理”做定向回滚：恢复真实 OpenAI、MongoDB、ChromaDB 适配器和对应集成测试骨架，同时保留已经完成的 SQL AST 安全校验、SQLite 业务数据集和 40 条 business benchmark。

这次不是整体回退最近提交，而是按文件恢复被误删或过度收敛的外部服务接入能力，避免把有价值的 benchmark 和安全能力一起撤销。

## 完成内容

### 1. 恢复真实 LLM Adapter

恢复 `sql_agent/llm/openai_llm.py`：

- 支持 OpenAI Chat Completions。
- 支持 Azure OpenAI。
- 支持 embedding。
- 支持 token 统计。

`Settings` 中补回 `AZURE_OPENAI_API_VERSION`，避免 Azure OpenAI 初始化时缺少 `azure_api_version`。

### 2. 恢复文档存储和向量存储 Adapter

恢复 `MongoStorage`：

- 支持 insert、find_one、find、update、delete。
- 将 MongoDB `_id` 标准化为字符串，并补齐 `id` 字段，方便上层统一处理。

恢复 `ChromaVectorStore`：

- 支持集合创建、写入、查询和删除。
- 查询时按 `db_connection_id` 过滤。
- 写入 golden SQL 时提取 SQL 使用表信息作为 metadata。

同时保留内存存储类，供轻量测试或局部模块测试使用。

### 3. 恢复真实集成测试骨架

恢复 `tests/test_real_integrations.py`：

- `test_real_openai_llm_can_generate_and_embed`
- `test_real_mongodb_storage_roundtrip`
- `test_real_chromadb_vector_store_roundtrip`

这些测试默认跳过，需要显式设置：

```bash
RUN_REAL_INTEGRATIONS=true
```

并配置对应外部服务环境变量后才会运行。

### 4. 保留原型稳定测试链路

本次回滚没有撤销以下能力：

- `sql_agent/security/` 中的 `sqlglot` AST 安全校验。
- `sql_agent/eval/demo_business.py` 中的 SQLite 业务数据集构造器。
- `eval_cases/business_benchmark.yml` 中的 40 条业务 benchmark。
- `eval_cases/business_semantic_model.yml` 中的业务语义模型。
- Evaluation Harness 对 `difficulty`、`expected_status`、`golden_sql` 等字段的支持。

也就是说，项目现在的定位是：

- 本地可复现链路：SQLite benchmark 和稳定测试替身。
- 可扩展接入链路：OpenAI、MongoDB、ChromaDB adapter 保留并可通过环境变量启用。

## 文档同步

已同步更新：

- `README.md`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
- `docs/study-plan/`
- 历史迭代记录中的测试状态描述

重点修正：

- 不再描述为“只保留 MockLLM、内存存储和 SQLite benchmark”。
- 改为“SQLite + 稳定测试替身是默认可复现测试路径，真实 adapter 已保留，集成测试默认跳过”。
- 避免把当前项目误包装成已经生产可用的外部服务平台。

## 实现效果

回滚后，项目表达更准确：

1. **原型可复现。**
   SQLite 业务数据集和 business benchmark 仍然可以在本地稳定跑通，适合面试展示、回归测试和核心链路验证。

2. **架构可扩展。**
   真实 LLM、文档存储、向量存储 adapter 没有被删除，IoC 默认配置仍指向真实适配器，可以通过环境变量切换和外部服务联调。

3. **测试边界清晰。**
   本地单元测试和端到端测试不依赖真实外部服务；真实 adapter 测试以 skip 形式保留，需要凭据和服务环境时再显式开启。

## 测试结果

本次执行过的验证命令：

```bash
pytest tests/test_ioc_registry.py tests/test_real_integrations.py -q
python -m black sql_agent tests main.py
python -m ruff check sql_agent tests main.py
pytest tests -q
python -m compileall -q sql_agent tests main.py
git diff --check
```

结果：

```text
tests/test_ioc_registry.py + tests/test_real_integrations.py: 2 passed, 3 skipped, 1 warning
black: 91 files left unchanged
ruff: All checks passed
pytest tests -q: 134 passed, 3 skipped, 2 warnings
compileall: passed
git diff --check: passed
```

说明：

- 3 个 skipped 是真实 OpenAI、MongoDB、ChromaDB 集成测试，默认需要外部环境才运行。
- warnings 来自 FastAPI TestClient/httpx/starlette 依赖组合弃用提示，以及当前工作区 `.pytest_cache` 写入权限提示，不影响断言结果。

## 后续建议

当前更适合在简历和面试中表述为：

> 一个可本地复现的 Data Agent 原型，核心链路覆盖 Semantic Layer、SQL AST 安全、候选 SQL 执行证据排序、Grounded Result Analysis、Feedback/Evaluation Loop，并保留真实 OpenAI、MongoDB、ChromaDB adapter 作为可扩展接入点。

不建议表述为：

> 已完整落地生产级多租户数据智能平台。

生产化还需要继续补充：

- 真实权限系统和数据库只读账号治理。
- 行列级权限与敏感字段脱敏。
- 查询资源配额、超时、限流和审计。
- 多环境配置管理和密钥托管。
- 真实业务数据上的 benchmark 与人工审核闭环。

## 涉及文件

- `sql_agent/core/config.py`
- `sql_agent/llm/base.py`
- `sql_agent/llm/openai_llm.py`
- `sql_agent/storage/db.py`
- `sql_agent/storage/vector.py`
- `tests/test_real_integrations.py`
- `tests/test_ioc_registry.py`
- `requirements.txt`
- `README.md`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
- `docs/study-plan/`
- `docs/iterations/`
