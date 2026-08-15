# 2026-08-15 11:15:55 SQL AST Safety + Business Benchmark

## 本次目标

本次迭代实施路线 B：引入 `sqlglot` AST 级 SQL 安全校验，并构造可复现的 SQLite 业务 benchmark。目标是让项目从“能生成和执行 SQL”进一步升级为“能解释安全边界、能在固定业务数据集上做回归评估”的 Data Agent 原型。

## 完成内容

### 1. SQL AST 安全校验

新增 `sql_agent/security/` 模块：

- `SQLSafetyPolicy`：定义只读、CTE、子查询、`SELECT *`、函数黑白名单和 schema 范围策略。
- `SQLSafetyReport`：输出 allowed、risk_level、normalized_sql、引用表、引用列和 violations。
- `SQLSafetyValidator`：基于 `sqlglot` 解析 SQL AST，校验非 SELECT、多语句、未知表、未知列、歧义未限定列、投影 `SELECT *`、危险函数、alias、JOIN、CTE 和子查询作用域。

关键修正：

- `COUNT(*)` 不再被误判为 `SELECT *`；只拦截投影展开星号。
- CTE 内部列解析按最近 `SELECT` 作用域判断，避免外层表污染子查询列归属。
- CTE 输出列引用不重复按物理表校验，物理列在 CTE 定义处校验。

### 2. 工具层和候选排序接入安全报告

`AgentToolkit.SqlDbQuery` 执行前统一调用 `SQLSafetyValidator`，替换旧的 SQL 元数据解析 / regex SQL 校验路径。

`CandidateRanker` 对每条候选 SQL 增加 `safety` 证据：

- 有效候选会保留安全通过报告。
- 无效候选会在 `evidence` / `selection_reason` 中展示 AST 安全失败原因。
- CandidateRanker 为了兼容“列出明细”的历史行为，策略上允许 `SELECT *` 参与排序；工具层执行仍使用更严格默认策略。

同时清理了不再调用的旧 SQL regex 校验逻辑，避免两套安全判断并存。

### 3. SQLite 业务数据集

新增 `BusinessDemoBuilder`，构造确定性 SQLite 数据库：

- `departments`
- `employees`
- `customers`
- `products`
- `orders`
- `order_items`
- `refunds`
- `web_events`

数据覆盖销售、客户、商品、退款、组织和站内行为等常见企业分析场景，适合作为原型阶段的 business benchmark。

### 4. Business Semantic Model + 40 条 Benchmark

新增：

- `eval_cases/business_semantic_model.yml`
- `eval_cases/business_benchmark.yml`
- `eval_cases/README.md`

语义模型覆盖：

- 指标：`gmv`、`net_revenue`、`paid_order_count`、`refund_amount`、`gross_margin`
- 维度：`order_month`、`customer_region`、`customer_segment`、`product_category`、`sales_channel`、`employee_department`
- 关系：订单、客户、订单明细、商品、员工、部门、退款之间的 Join 关系

benchmark 共 40 条问题，覆盖：

- `basic`
- `semantic`
- `join`
- `trend`
- `analysis`
- `visualization`
- `safety`

前 10 条带可执行 `golden_sql`，用于验证 SQLite 原型数据上的业务 SQL 口径。

### 5. Evaluation Harness 扩展

`EvaluationCase` 新增字段：

- `difficulty`
- `expected_status`
- `expected_columns`
- `expected_row_count`
- `expected_any_row`
- `forbidden_sql_contains`
- `golden_sql`

`EvaluationReport` 新增：

- `difficulty_metrics`

现在可以从 `eval_cases/business_benchmark.yml` 直接加载 40 条用例，并按 tag 和 difficulty 分桶统计 valid/execution/grounding 指标。

### 6. 数据库方言修复

修复 `SQLDatabase.dialect`：

- 之前返回 SQLAlchemy dialect 类字符串，传给 `sqlglot` 会报 unknown dialect。
- 现在使用 `engine.dialect.name`，SQLite 会稳定返回 `sqlite`。

同时规范化 SQLite 默认 schema：

- `main` / `temp` 不再暴露为 `main.orders`，而是返回裸表名 `orders`。
- Postgres 等真实 schema 仍保留 `schema.table`。

## 实现效果

本次迭代后，项目在面试表达上新增两个更硬的亮点：

1. **SQL 安全不是 regex 拦截，而是 AST 安全策略。**
   系统能解释每条 SQL 被允许或拒绝的具体原因，候选排序也能返回结构化 safety evidence。

2. **Benchmark 不是空泛评测，而是有可执行业务数据集。**
   项目可以用一套固定 SQLite 数据模拟企业经营分析问题，验证业务指标、Join、趋势、可视化和安全场景。

这使项目从“功能堆叠型 demo”更接近“有安全边界、有评估基准、有可复盘证据的 Agent 原型”。

## 测试结果

本次执行的验证命令：

```bash
python -m black sql_agent tests main.py
python -m ruff check sql_agent tests main.py
pytest tests -q
python -m compileall -q sql_agent tests main.py
git diff --check
```

结果：

```text
ruff: All checks passed
pytest tests -q: 历史模块测试已通过；后续已删除外部服务测试。
compileall: passed
git diff --check: passed
```

说明：

- 后续清理迭代已删除外部服务测试，当前测试以 SQLite + MockLLM 原型链路为准。
- warnings 包含 FastAPI/TestClient 依赖组合的弃用提示，以及当前工作区 `.pytest_cache` 写入权限提示。
- `git diff --check` 只提示 Windows 行尾转换 warning，不存在尾随空白错误。

## 边界和后续建议

当前 AST 安全校验覆盖了原型最关键的 SQL 安全面，但还不是完整生产权限系统。后续生产化建议继续补：

- 数据库只读账号和事务级只读保护。
- 行列级权限策略。
- 查询超时、扫描行数、结果行数和资源配额限制。
- 多数据库方言差异测试。
- 安全拒绝样例的误杀率/漏杀率评估。
- benchmark 的 `golden_sql` 扩展到全部非 safety 用例，并补充 expected result 快照。

## 涉及文件

- `sql_agent/security/`
- `sql_agent/agent/tools.py`
- `sql_agent/ranking/candidate.py`
- `sql_agent/ranking/ranker.py`
- `sql_agent/sql/database.py`
- `sql_agent/eval/demo_business.py`
- `sql_agent/eval/harness.py`
- `eval_cases/business_semantic_model.yml`
- `eval_cases/business_benchmark.yml`
- `eval_cases/README.md`
- `tests/test_sql_ast_safety.py`
- `tests/test_business_benchmark_dataset.py`
- `tests/test_agent_tools.py`
- `tests/test_candidate_ranking.py`
- `tests/test_eval_benchmark_2.py`
- `tests/test_sql_database.py`
- `README.md`
- `docs/project-highlights.md`
- `docs/interview-prep-sql-agent.md`
