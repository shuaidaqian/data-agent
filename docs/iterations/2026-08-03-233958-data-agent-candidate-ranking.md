# 2026-08-03 23:39:58 Data Agent 候选排序与证据化增强迭代记录

> 历史记录说明：本文记录的是 CandidateRanker 1.0 当次迭代状态。当前项目已经升级到 CandidateRanker 2.0，支持 `score_breakdown`、`selection_reason`、`source`、`result_shape`、verified query bonus 和 semantic plan match bonus，详见 `docs/iterations/2026-08-13-230519-data-agent-2-0-deepening.md`。

## 本次目标

参考 `HKUSTDial/awesome-data-agents` 中对 L2 数据 Agent 的能力划分，将当前 NL-to-SQL 原型从“单次 SQL 生成”推进到更像 Data Agent 的链路：多候选、可执行验证、证据化排序、Schema 语义增强。

本次不扩展前端、不引入大型多 Agent 框架，优先在现有后端架构中补强最能体现 Agent 工程能力的部分。

## 设计取舍

1. 先做候选 SQL Ranking，而不是完整多 Agent 系统
   - 当前项目已经有 `ReActAgent`、`PlanSolveAgent`、`Evaluator`、`SQLDatabase` 和工具白名单。
   - 候选排序可以最大化复用已有模块，风险和改动面较小。
   - 面试表达上也更直观：系统不盲信第一次 LLM 输出，而是执行、校验、评分、选择。

2. Schema 增强先做启发式，不先调用 LLM
   - 当前 `SchemaScanner` 已经能采样列值。
   - 通过列名、类型、主外键、低基数样本即可生成基础语义标签。
   - 这样测试稳定，不依赖外部 LLM。

3. API 做兼容式扩展
   - `/api/v1/question` 保持原有 `sql/status/confidence_score` 字段。
   - 新增可选 `candidates` 字段，包含每个候选 SQL 的状态、分数、执行证据和评分构成。
   - 旧调用方不需要改动。

## 已完成内容

1. 新增候选 SQL 排序模块
   - 新增 `sql_agent/ranking/candidate.py`
     - `CandidateExecution`：记录执行是否成功、行数、列名、结果预览、错误。
     - `SQLCandidate`：记录 SQL、状态、分数、证据、来源和评分构成。
   - 新增 `sql_agent/ranking/generator.py`
     - 从主 SQL 和中间步骤文本中抽取 fenced SQL block。
     - 对 SQL 候选做规范化去重。
   - 新增 `sql_agent/ranking/ranker.py`
     - 执行危险 SQL 拦截。
     - 校验表名是否在扫描得到的 schema 白名单中。
     - 执行候选 SQL 并收集结果证据。
     - 按 schema、执行成功、SQL 基础结构、问题意图和 Evaluator 分数综合排序。

2. 增强 SchemaScanner 列级语义
   - `ColumnMetadata` 新增字段：
     - `semantic_type`
     - `synonyms`
     - `distinct_count`
     - `null_count`
   - `SchemaScanner` 新增列统计采集：
     - distinct 数量。
     - null 数量。
   - `SchemaScanner` 新增语义推断：
     - 外键：`foreign_key`
     - 主键/id：`identifier`
     - 日期时间：`date`
     - 金额、价格、工资、数量：`measure`
     - name/title/label：`name`
     - 低基数或 status/category/type：`category`
     - 其他：`text`
   - `table_schema` 中追加语义注释，帮助 Agent 在 prompt 中拿到列级上下文。

3. `/api/v1/question` 接入候选证据
   - Agent 生成 SQL 后，API 会收集主 SQL 和中间步骤中的候选 SQL。
   - 使用 `CandidateRanker` 对候选做执行验证和排序。
   - 返回 `candidates` 列表。
   - 最优候选会成为最终返回的 `sql`。
   - `confidence_score` 改为来自最优候选综合分，语义更接近“系统选择置信度”。

4. 新增测试
   - `tests/test_candidate_ranking.py`
     - 覆盖候选排序选择可执行聚合 SQL。
     - 覆盖非法表名候选被标记为 `INVALID`。
     - 覆盖候选 SQL 去重。
   - `tests/test_schema_scanner_samples.py`
     - 补充列语义类型和同义词断言。
   - `tests/test_api_e2e.py`
     - 补充 `/api/v1/question` 返回候选证据的端到端断言。

## 测试结果

新增功能定向测试：

```powershell
pytest tests/test_candidate_ranking.py tests/test_schema_scanner_samples.py tests/test_api_e2e.py -q
```

结果：

```text
6 passed, 2 warnings
```

完整根目录模块测试：

```powershell
pytest tests -q
```

结果：

```text
历史模块测试已通过；后续已删除外部服务测试。
```

语法编译检查：

```powershell
python -m compileall -q sql_agent tests main.py
```

结果：退出码 `0`，无语法编译错误。

说明：

- 后续清理迭代已删除外部服务测试，测试重点收敛到 SQLite + MockLLM 原型链路。
- warnings 仍来自 FastAPI TestClient/httpx 组合弃用提示和 `.pytest_cache` 写入权限提示。

## 效果分析

1. 从“单 SQL 输出”升级为“候选决策”
   - 过去 API 直接返回 Agent 的第一条 SQL。
   - 现在会保留候选、执行候选、解释评分依据，再选择最优 SQL。
   - 这让系统具备更明显的 Agent 决策过程，而不是简单 prompt wrapper。

2. 从“能执行”升级为“有证据”
   - 候选结果中包含执行行数、结果列、预览和错误。
   - 面试时可以直接展示为什么选择某条 SQL、为什么拒绝另一条 SQL。

3. Schema 从“结构信息”升级为“语义信息”
   - 列不再只有 name/type/sample values。
   - 现在有 semantic type、synonyms、distinct/null 统计。
   - 后续可以自然接向量召回、业务术语映射和 schema memory。

4. 为 Proto-L3 Data Agent 铺路
   - 当前仍是 L2 风格的数据 Agent：环境感知、工具调用、记忆、执行反馈。
   - 候选排序和证据选择是向 L3 任务编排过渡的基础。
   - 后续可以把 Ranking、Correction、Schema Enrichment 串成可配置 task graph。

## 后续建议

1. 将 `CandidateGenerator` 扩展为真正的多候选生成
   - 当前主要收集主 SQL 和中间步骤 SQL。
   - 下一步可让 LLM 按不同策略生成多个候选：
     - conservative
     - join-aware
     - aggregation-first
     - CTE-based

2. 加强复杂 SQL 白名单
   - 当前候选排序校验表名，工具层对单表做简单列名校验。
   - 后续可引入 SQL AST，处理 alias、CTE、子查询和表达式列。

3. 将 Schema 语义写入向量库
   - 当前语义信息已经在 `TableDescription` 中。
   - 后续可写入 `ContextStore` 或 `VectorBackend`，支持自然语言术语召回列。

4. 增加自然语言解释层
   - 基于最佳候选的执行证据，生成一段面向用户的“选择理由”和“查询结果解释”。
   - 这会把项目进一步推向 Data Analysis Agent。
