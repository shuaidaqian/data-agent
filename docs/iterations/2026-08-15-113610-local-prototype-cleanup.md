# 2026-08-15 11:36:10 Local Prototype Cleanup

## 本次目标

将项目定位彻底收敛为可复现原型：默认链路只依赖 MockLLM、内存存储、SQLite 和 business benchmark，不再保留外部服务集成测试、默认外部服务实现和相关文档描述。

## 清理内容

### 1. 删除外部服务实现和测试

删除：

- 外部模型服务实现文件
- 外部服务集成测试文件

移除 requirements 中的外部服务依赖和旧 SQL 解析依赖。

保留 `LLMBackend`、`StorageBackend`、`VectorBackend` 抽象接口，方便后续需要时接入真实实现，但当前原型不默认依赖这些服务。

### 2. 默认 IoC 改为本地原型实现

`System` 默认组件调整为：

- `LLMBackend` -> `sql_agent.llm.mock_llm.MockLLM`
- `StorageBackend` -> `sql_agent.storage.db.InMemoryStorageBackend`
- `VectorBackend` -> `sql_agent.storage.vector.InMemoryVectorStore`

新增 `sql_agent/llm/mock_llm.py`，作为生产代码内的本地确定性 LLM 替身，不再依赖 `tests.fakes`。

### 3. 存储层和向量层本地化

`sql_agent/storage/db.py`：

- 删除外部文档库实现。
- 保留 `StorageBackend` 抽象。
- 将 `InMemoryStorageBackend` 作为默认实现。

`sql_agent/storage/vector.py`：

- 删除外部向量库实现。
- 保留 `VectorBackend` 抽象。
- 新增 `InMemoryVectorStore`，使用轻量 token overlap 做本地检索。

### 4. 文档口径统一

更新范围：

- `README.md`
- `ARCHITECTURE.md`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
- `docs/study-plan/`
- `docs/iterations/`

统一后的项目描述：

- 这是一个 MockLLM + SQLite + business benchmark 的可复现 Data Agent 原型。
- 默认不访问外部服务，不需要外部服务凭据。
- 测试重点是 API 端到端链路、SQL AST 安全、business benchmark、Semantic Layer、CandidateRanker、ResultAnalyzer 和 Visualization。
- IoC 保留可替换接口，但不再把外部服务实现作为默认项目能力宣传。

### 5. 测试调整

新增 IoC 默认实现测试：

- `tests/test_ioc_registry.py::test_ioc_defaults_use_local_prototype_components`

验证默认配置不再指向外部服务实现。

## 当前效果

清理后，项目更符合“秋招项目原型”的讲法：

- 不夸大生产级外部服务集成。
- 默认环境更轻，不需要模型 API key、外部文档库或外部向量库。
- SQLite business benchmark 成为项目评估的主要抓手。
- 外部模型和持久化后端被表述为未来可替换方向，而不是当前已完成能力。

## 验证结果

本次执行：

```bash
python -m black sql_agent tests main.py
python -m ruff check sql_agent tests main.py
pytest tests -q
```

结果：

```text
black: 90 files left unchanged
ruff: All checks passed
pytest tests -q: 134 passed, 2 warnings
```

说明：

- 当前测试已经没有外部服务 skipped。
- warnings 来自 FastAPI TestClient/httpx 组合提示，以及当前工作区 `.pytest_cache` 权限提示。

## 后续建议

后续如果要继续增强，优先做与原型定位一致的方向：

- 扩展 business benchmark 的 golden SQL 和 expected result。
- 补充更多 SQLite 业务域数据。
- 继续强化 SQL AST 权限和资源限制。
- 增加 benchmark 报告中的失败 case 明细。
- 若未来真的接真实模型或持久化后端，应作为独立 adapter 和可选集成，而不是默认路径。
