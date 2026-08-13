# 2026-08-09 22:32:26 Grounded Result Analysis 迭代记录

> 历史记录说明：本文记录的是 2026-08-09 当次迭代状态，测试数量和后续计划保留当时事实。当前项目已经在 2026-08-13 迭代升级到 Data Agent 2.0，详见 `docs/iterations/2026-08-13-230519-data-agent-2-0-deepening.md`。

## 本轮目标

本轮目标是把 `/api/v1/question` 从“返回一条 SQL”推进到“返回可追溯的数据答案”：

1. 先把最优候选 SQL 的执行结果透出到 API。
2. 再实现启发式 `ResultAnalyzer`，稳定生成 `answer`、`summary` 和 `key_findings`。
3. 最后接入 `LLMResultAnalyzer`，让回答更自然，但必须严格 grounded。

开发时的需求拆解：

- 用户真正要的是问题答案，不是 SQL 字符串。
- SQL 是取数计划，SQL 执行结果才是回答依据。
- LLM 不能直接执行 SQL，也不能直接访问数据库连接。
- 系统负责执行 SQL，LLM 只能基于受控 SQL result 做表达。
- 每个分析结论必须能追溯到 SQL result evidence。

开发时的风险审查：

- 如果 LLM 生成了不可解析 JSON，不能接受。
- 如果 LLM 给出关键发现但没有 evidence，不能接受。
- 如果 LLM 在 `answer`、`summary` 或 `key_findings.claim` 里编造 SQL result 中不存在的数值，不能接受。
- 如果结果为空或 SQL 执行失败，不能让 LLM 补业务结论。

## 实现内容

### 1. API 透出最优候选执行结果

`/api/v1/question` 在候选 SQL 排序后，会取 `ranked_candidates[0]` 作为最优候选。

当最优候选状态为 `VALID` 时，API 会基于 `best_candidate.execution` 返回：

```json
{
  "result": {
    "columns": ["cnt"],
    "rows": [{"cnt": 1}],
    "row_count": 1,
    "truncated": false
  }
}
```

这里没有重复执行 SQL，而是复用 `CandidateRanker` 阶段已经得到的受控执行结果，避免同一个请求内重复查询数据库，也保证最终答案和候选排序证据来自同一份结果。

### 2. 新增分析数据结构

新增 `sql_agent/analysis/types.py`：

- `QueryResultPayload`：对外暴露的 SQL 执行结果快照。
- `KeyFinding`：带 evidence 的关键发现。
- `AnalysisResult`：统一承载 `answer`、`result`、`summary`、`key_findings`、`limitations` 和 `followup_questions`。

这些结构让 API 返回保持稳定，也为后续图表推荐、洞察生成、报告生成留下扩展点。

### 3. 实现 HeuristicResultAnalyzer

新增 `HeuristicResultAnalyzer`：

- SQL 执行失败：返回“无法基于数据给出答案”，并把错误写入 limitations。
- 空结果：返回“本次查询没有返回数据”，不生成关键发现，避免从空结果推断业务原因。
- 单行单列：生成稳定答案，例如 `当前查询结果为 4。`，并附带 `SQL result: cnt = 4` evidence。
- 多行多列：返回结果规模、列信息，并提取简单数值发现，例如最高值所在行。

这个分析器不依赖 LLM，因此适合作为默认实现和 LLM 失败时的兜底。

### 4. 实现 LLMResultAnalyzer

新增 `LLMResultAnalyzer`：

- 只把用户问题、已执行 SQL 和 `QueryResultPayload` 发给 LLM。
- 不传数据库连接。
- 不允许 LLM 执行 SQL。
- 要求 LLM 只返回 JSON，不返回 markdown。
- 要求每个 `key_findings` 条目包含 `evidence`。
- 要求 evidence 以 `SQL result:` 开头，并且能从返回行中找到对应列和值。
- 校验 `answer`、`summary` 和 `key_findings.claim` 中出现的数值必须存在于 SQL result 行值或 `row_count` 中。
- 任一校验失败，自动回退到 `HeuristicResultAnalyzer`。

这使 LLM 的角色变成“表达层”，而不是“事实来源”。

### 5. 配置开关

新增环境变量：

```text
RESULT_ANALYZER=heuristic
```

默认使用启发式分析器。设置为：

```text
RESULT_ANALYZER=llm
```

时，API 会启用严格 grounded 的 LLM 分析器。

### 6. API 返回结构升级

当前 `/api/v1/question` 典型返回：

```json
{
  "answer": "当前查询结果为 1。",
  "sql": "SELECT COUNT(*) AS cnt FROM employees",
  "status": "VALID",
  "confidence_score": 0.85,
  "result": {
    "columns": ["cnt"],
    "rows": [{"cnt": 1}],
    "row_count": 1,
    "truncated": false
  },
  "analysis": {
    "summary": "SQL 返回 1 行 1 列，核心指标 `cnt` 的值为 1。",
    "key_findings": [
      {"claim": "cnt = 1", "evidence": "SQL result: cnt = 1"}
    ],
    "limitations": ["该结论仅基于当前数据库快照。"],
    "followup_questions": ["是否需要按类别或部门进一步拆分？"]
  },
  "candidates": [
    {
      "sql": "SELECT COUNT(*) AS cnt FROM employees",
      "status": "VALID",
      "score": 0.85,
      "evidence": "执行成功，返回 1 行；结果列：cnt；评分构成：..."
    }
  ]
}
```

## 测试覆盖

新增和更新的测试覆盖：

- 启发式分析器对单指标结果生成稳定答案。
- 启发式分析器对空结果不编造结论。
- LLM 分析器接受带 grounded evidence 的 JSON。
- LLM 分析器在缺少 evidence 时回退。
- LLM 分析器在 answer/summary 编造未出现在 SQL result 中的数字时回退。
- API 端到端返回 `answer`、`result`、`analysis` 和 `candidates`。
- API 在 `RESULT_ANALYZER=llm` 时返回 grounded 的 LLM 自然语言答案。

本轮验证命令：

```powershell
pytest tests/test_result_analysis.py -q
pytest tests -q
python -m compileall -q sql_agent tests main.py
```

当前验证结果：

```text
90 passed, 3 skipped, 2 warnings
compileall exit 0
```

其中 3 个 skipped 是真实 OpenAI、MongoDB、ChromaDB 集成测试，需要在具备外部服务和凭据的环境中通过 `RUN_REAL_INTEGRATIONS=true` 显式执行。2 个 warnings 分别来自当前 FastAPI TestClient/httpx 组合的弃用提示，以及当前工作区 `.pytest_cache` 写入权限提示。

## 实现效果

本轮完成后，项目的对外能力发生了一个关键变化：

- 过去：用户问问题，系统主要返回 SQL 和候选证据。
- 现在：用户问问题，系统返回自然语言答案、SQL、SQL 执行结果、分析证据和候选排序过程。

这让项目更符合 Data Agent 的产品形态：业务用户看到的是答案，工程侧仍保留 SQL 和 evidence 作为审计依据。

面试时可以这样讲：

> 我没有让 LLM 直接回答数据库问题，而是让系统先生成、校验、执行和排序 SQL，拿到受控 SQL result 后再生成答案。LLM 只负责表达，所有关键发现必须带 `SQL result:` evidence，不可信输出会回退到启发式分析。

## 风险与边界

当前实现仍然保持原型边界：

1. 启发式分析器只做基础单指标、多行摘要和简单数值发现，不做复杂统计推断。
2. LLM grounded 校验主要覆盖 evidence 和数值事实，复杂因果句、趋势归因仍需要更细粒度的结论类型约束。
3. 多行结果目前只返回 preview，`truncated=true` 时不能对未返回数据做完整分布判断。
4. 候选 SQL 语义正确性仍需要 CandidateRanker、Evaluator、few-shot 和测试集共同提升，ResultAnalyzer 只保证“基于已选 SQL 的结果不要被解释歪”。
5. 生产化还需要只读账号、查询超时、权限审计、敏感字段脱敏和 Agent trace。

## 后续建议

下一步最有价值的方向：

1. 引入 SQL AST 级表列解析，提升 alias、CTE、子查询的白名单校验准确率。
2. 支持多策略主动候选生成，而不只从 Agent 输出和中间步骤中收集候选。
3. 给 ResultAnalyzer 增加结论类型约束，例如单指标、Top-K、趋势、对比、异常值。
4. 输出图表推荐和 ECharts/Vega-Lite spec，让数据答案进一步变成可展示洞察。
5. 接入 Langfuse 或 LangSmith，记录 Prompt、Action、Observation、候选 SQL、执行结果、分析结果和回退原因。
