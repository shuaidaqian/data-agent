# SQL Agent 秋招面试准备指南

## 目标

你现在最需要做的不是继续堆功能，而是把这个项目从“我写过代码”转成“我能像项目负责人一样解释它”。

面试官拷问时通常不会只问“用了什么技术”，而是会沿着这些问题追：

1. 这个项目解决什么业务问题？
2. 为什么不用普通 BI、规则 SQL 或 LangChain 现成 Agent？
3. 你负责了什么？
4. 核心链路怎么跑？
5. 难点在哪里？
6. SQL 生成错了怎么办？
7. 怎么保证安全？
8. 怎么评估效果？
9. 如果上线，会有哪些风险？
10. 这个项目和真实企业数据场景有什么关系？

你的准备目标是：

> 任何一个模块被问到，都能从业务动机、架构设计、代码实现、测试验证、缺陷边界五个层面讲清楚。

## 实习项目包装边界

如果准备把它包装成神州数码实习项目，表述要稳，不要说成“我主导上线了完整生产级 NL2SQL 平台”，这样容易被追问穿。

更安全、也更像实习生真实经历的说法是：

> 在神州数码实习期间，我参与了一个面向企业数据库问答的 Data Agent 原型项目，目标是降低业务人员写 SQL 和理解查询结果的门槛。我主要负责核心 NL-to-SQL / NL-to-data-answer Agent 链路的设计与实现，包括 Schema 扫描、Agent 工具调用、多轮上下文、SQL 自纠错、候选 SQL 执行验证、证据化排序和基于执行结果的 grounded 结果分析。项目以原型验证和内部 PoC 为主，使用 FastAPI、SQLAlchemy、OpenAI 接口、MongoDB/ChromaDB 抽象存储等技术栈。

这样讲的好处：

- “原型 / PoC / 内部验证”符合项目目前成熟度。
- “主要负责核心链路”能突出贡献，但不会夸大成全公司生产系统。
- “参考 Dataherald 架构重构”可以说成“调研开源 Dataherald 后做轻量化设计”，体现技术调研能力。
- 不要虚构上线指标、客户名称、真实数据库规模。如果面试官追问，可以说：“因为涉及公司数据，我本地复现时用了 SQLite 和模拟数据做端到端测试。”

## 一句话定位

这个项目可以定位为：

> 一个参考 Dataherald 架构并结合 Data Agent 思路重构的轻量级 NL-to-SQL / NL-to-data-answer Agent 系统。它不是简单让 LLM 一次性生成 SQL，而是把数据库环境感知、工具调用、Schema Linking、多轮记忆、执行反馈自纠错、候选 SQL 证据化排序和 grounded 结果分析串成一个可测试的工程闭环。

更面试化的版本：

> 这个项目的亮点不是“我调了一个大模型生成 SQL”，而是“我围绕 LLM 不可靠这个事实，设计了 schema 感知、工具约束、执行反馈、自纠错、候选证据排序和结果 grounded 分析这一整套工程闭环”。

## 必须背熟的主链路

你要能闭眼画出这条链路：

```text
用户问题
-> FastAPI /api/v1/question
-> Prompt + Conversation
-> 从存储加载 DatabaseConnection
-> SQLAlchemy 连接数据库
-> SchemaScanner 扫描表、列、样本值、语义类型
-> ContextStore 检索 few-shot 和管理员指令
-> AgentSelector 选择 ReAct 或 PlanSolve
-> AgentToolkit 调用工具观察数据库
-> LLM 生成 SQL
-> DAIL/DIN 自纠错
-> CandidateRanker 执行验证和排序
-> ResultAnalyzer 基于最优候选执行结果生成 answer/summary/key_findings
-> API 返回最终 answer + SQL + result + analysis + candidates 证据
```

## 2 分钟项目故事

你要能在 2 分钟内讲清楚：

> 这个项目是为了解决企业内部业务人员不会写 SQL，但又需要查数和理解结果的问题。传统方案要么依赖数据分析师手写 SQL，要么 BI 报表不够灵活。我们做的是一个轻量级 NL-to-SQL / NL-to-data-answer Data Agent：用户输入自然语言问题，系统先扫描数据库 Schema，构造表、列、主外键、样本值和列语义信息，然后 Agent 通过受控工具获取相关表结构、执行 SQL、拿到反馈，再生成或修正 SQL。为了避免盲信 LLM 的第一次输出，我加入了候选 SQL 执行验证和证据化排序，让系统根据 schema 校验、执行结果和问题意图选择最优 SQL。最后，系统会把最优候选的执行结果透出给 API，并基于这份受控结果生成 answer、summary 和 key findings，所以用户拿到的是可追溯的数据答案，而不只是 SQL 字符串。

## 推荐阅读顺序

不要按文件夹乱读。按调用链读代码。

### 1. FastAPI 入口

文件：

- `main.py`

重点：

- FastAPI app 怎么创建。
- 路由怎么挂载。

### 2. 核心 API 链路

文件：

- `sql_agent/api/routes.py`

重点看 `/api/v1/question`：

- 请求体有哪些字段。
- 如何创建 `System`。
- 如何从 storage 取数据库连接。
- 如何创建 `Prompt` 和 `Conversation`。
- 如何扫描 schema。
- 如何调用 Agent。
- 如何做 correction。
- 如何做 candidate ranking。
- 返回结果包含什么。

### 3. 核心数据模型

文件：

- `sql_agent/core/types.py`

必须熟悉：

- `DatabaseConnection`
- `ColumnMetadata`
- `TableDescription`
- `Prompt`
- `Conversation`
- `SQLGeneration`
- `GoldenSQL`
- `Instruction`

### 4. IoC 配置层

文件：

- `sql_agent/core/config.py`

必须理解：

- 为什么抽象 `LLMBackend`。
- 为什么抽象 `StorageBackend`。
- 为什么抽象 `VectorBackend`。
- 环境变量如何替换实现。
- 对企业项目的意义：可插拔、可替换、方便测试。

### 5. SchemaScanner

文件：

- `sql_agent/sql/scanner.py`

重点：

- 怎么用 SQLAlchemy inspector 扫表。
- 怎么识别主键和外键。
- 怎么采样列值。
- 怎么算 `distinct_count` 和 `null_count`。
- 怎么推断 `semantic_type` 和 `synonyms`。

### 6. Agent 工具层

文件：

- `sql_agent/agent/tools.py`

重点：

- `SqlDbQuery`
- `DbTablesWithRelevanceScores`
- `DbRelevantTablesSchema`
- `DbColumnEntityChecker`
- `DbRelevantColumnsInfo`
- schema 白名单怎么做。
- 危险 SQL 怎么拦截。

### 7. ReAct Agent

文件：

- `sql_agent/agent/react_agent.py`

重点：

- Thought
- Action
- Action Input
- Observation
- Final SQL

你要能讲清楚：为什么自己实现 ReAct loop，而不是完全依赖 LangChain。

### 8. Plan-and-Solve Agent

文件：

- `sql_agent/agent/plan_solve_agent.py`

重点：

- 复杂 SQL 为什么要先规划。
- 规划阶段分析哪些内容。
- 规划结果如何指导工具调用。

### 9. SQL 自纠错

文件：

- `sql_agent/correction/dail_style.py`
- `sql_agent/correction/din_style.py`

重点：

- DAIL 风格：execute-feedback-fix。
- DIN 风格：verify-then-fix。
- SQL 错了以后系统怎么修。

### 10. 候选 SQL 排序

文件：

- `sql_agent/ranking/ranker.py`

这是最新亮点，必须吃透：

- 为什么需要多候选。
- 怎么校验候选。
- 怎么执行候选。
- 怎么收集证据。
- 怎么排序。
- 为什么这比直接返回 LLM 第一条 SQL 更可靠。

### 11. 结果分析层

文件：

- `sql_agent/analysis/result_analyzer.py`
- `sql_agent/analysis/types.py`

这是把项目从 SQL 生成推进到数据问答的最新亮点，必须吃透：

- `HeuristicResultAnalyzer` 如何基于执行结果生成稳定答案。
- `LLMResultAnalyzer` 为什么不能接触数据库连接，只能消费 SQL result。
- `key_findings.evidence` 为什么必须能追溯到 `SQL result:`。
- LLM 输出无法解析、缺少 evidence 或出现未出现在 SQL result 中的数值时为什么要回退。
- 为什么“系统执行 SQL，LLM 分析结果”比“LLM 执行 SQL 并分析”更安全。

## 必做实验

你要自己跑一遍 demo，并故意制造错误。这样面试时讲起来才有底气。

### 实验 1：正常查询

问题：

```text
员工数量是多少？
```

期望 SQL：

```sql
SELECT COUNT(*) AS cnt FROM employees
```

你要能解释：

- 为什么 `COUNT(*)` 比 `SELECT *` 更符合“数量是多少”。
- `candidates` 中会包含 SQL、status、score、evidence、execution.row_count、execution.columns。
- `result` 中会包含 `columns=["cnt"]`、`rows=[{"cnt": 1}]`。
- `analysis.key_findings` 中必须有类似 `SQL result: cnt = 1` 的证据。

### 实验 2：非法表名

非法候选：

```sql
SELECT COUNT(*) FROM payroll
```

预期：

- 被拒绝。
- 原因是 `payroll` 不在扫描到的 schema 白名单中。

可以回答的问题：

> 如果 LLM 幻觉了一个表怎么办？

回答：

> 不会直接执行。候选排序和工具层都会做 schema 白名单校验，表名必须来自 `TableDescription`，否则标记为 `INVALID`，并把原因写进 evidence。

### 实验 3：危险 SQL

危险 SQL：

```sql
DROP TABLE employees
```

预期：

- `SQLDatabase.parser_to_filter_commands()` 会拦截危险模式。

可以回答的问题：

> 如果模型生成了危险 SQL 怎么办？

回答：

> SQL 执行层有危险命令过滤，工具层还有 schema 白名单，形成两层防护。后续生产化还可以接权限系统和 SQL AST 级审计。

### 实验 4：LLM 分析器编造数字

模拟 LLM 返回：

```json
{
  "answer": "当前员工总数为 999 人。",
  "key_findings": [
    {"claim": "cnt = 4", "evidence": "SQL result: cnt = 4"}
  ]
}
```

预期：

- 系统不会接受这个回答。
- 因为 `999` 没有出现在 SQL result 中。
- `LLMResultAnalyzer` 会回退到启发式答案：`当前查询结果为 4。`

可以回答的问题：

> 如果 LLM 解释 SQL 结果时又幻觉了怎么办？

回答：

> 我把 LLM 限制成表达层，不让它执行 SQL，也不让它拿数据库连接。它只能消费系统执行后的 SQL result。分析器会校验每个 key finding 的 evidence，还会检查回答、摘要、结论里的数字是否出现在 SQL result 中；如果不满足，就回退到启发式分析。

## 重点测试文件

测试就是项目说明书。重点看：

- `tests/test_api_e2e.py`：API 端到端。
- `tests/test_candidate_ranking.py`：候选 SQL 排序。
- `tests/test_result_analysis.py`：结果分析、grounded evidence 和 LLM 回退。
- `tests/test_schema_scanner_samples.py`：schema 语义增强。
- `tests/test_agent_tools.py`：工具层和白名单。
- `tests/test_conversation.py`：多轮会话。

当前测试结果要记住：

```text
90 passed, 3 skipped, 2 warnings
```

面试时可以说：

> 我用 SQLite + MockLLM 做了端到端测试，这样核心链路不依赖真实 OpenAI 也能稳定回归。真实 OpenAI、MongoDB、ChromaDB 集成测试也保留了测试骨架，但默认跳过，需要有凭据时显式执行。

## 3 天快速吃透计划

### 第一天：只看主链路

目标：

> 能从 `/api/v1/question` 讲到最终返回。

任务：

1. 画出完整调用链。
2. 读 `sql_agent/api/routes.py`。
3. 读 `sql_agent/core/types.py`。
4. 跑：

```powershell
pytest tests/test_api_e2e.py -q
```

5. 手写一遍请求响应 JSON。

当天必须能回答：

> 用户问一句话后，系统内部发生了什么？

### 第二天：吃透三大亮点

目标：

> 能讲清楚为什么这个项目不是普通 CRUD 或 prompt demo。

任务：

1. 读 `sql_agent/sql/scanner.py`。
2. 读 `sql_agent/agent/tools.py`。
3. 读 `sql_agent/ranking/ranker.py`。
4. 读 `sql_agent/analysis/result_analyzer.py`。
5. 跑：

```powershell
pytest tests/test_schema_scanner_samples.py -q
pytest tests/test_agent_tools.py -q
pytest tests/test_candidate_ranking.py -q
pytest tests/test_result_analysis.py -q
```

当天必须能回答：

- 怎么降低 LLM 幻觉？
- 怎么保证 SQL 安全？
- 为什么候选排序比直接返回 SQL 更好？
- 为什么最终答案必须基于 SQL result，而不是让 LLM 自由发挥？

### 第三天：准备面试话术和拷问

目标：

> 能用项目负责人的口吻讲设计取舍。

任务：

1. 读 `docs/project-highlights.md`。
2. 读 `docs/iterations/2026-08-03-233958-data-agent-candidate-ranking.md`。
3. 自己录音讲 3 分钟项目介绍。
4. 准备 10 个拷问问题的回答。
5. 重新跑：

```powershell
pytest tests -q
python -m compileall -q sql_agent tests main.py
```

当天必须能回答：

- 你在这个项目里最难的技术点是什么？
- 如果上线到真实企业数据库，你会怎么改？

## 3 分钟项目介绍模板

可以这样讲：

> 我在实习期间参与了一个企业数据库问答方向的 Data Agent 原型项目。背景是业务人员经常需要临时查数，但不会写 SQL，数据分析师响应成本比较高，所以我们希望做一个自然语言到 SQL 的 Agent。
>
> 我的主要工作是核心 NL-to-SQL / NL-to-data-answer 链路。我没有直接调用 LLM 生成 SQL，而是把系统拆成几层：首先通过 SQLAlchemy 扫描数据库 schema，包括表、列、主外键、样本值、distinct/null 统计和列语义类型；然后 Agent 根据问题复杂度选择 ReAct 或 Plan-and-Solve，通过受控工具获取相关表结构、检查列值、执行 SQL；生成 SQL 后再用执行反馈做 DAIL 风格自纠错。
>
> 后面我进一步加了候选 SQL 证据化排序和 grounded 结果分析。系统不会盲信 LLM 第一条输出，而是收集候选 SQL，做 schema 白名单校验、危险 SQL 拦截、真实执行，并根据执行结果、问题意图和评估分排序。API 返回最终 SQL 的同时，也返回 result、analysis 和 candidates。最终自然语言答案只基于系统执行 SQL 得到的结果，关键发现必须带 `SQL result:` evidence。
>
> 这个项目最后用 FastAPI 提供接口，用 SQLite + MockLLM 做了端到端测试，核心模块测试是 90 passed。它目前还是 PoC，但已经验证了一个企业级 NL-to-SQL Agent 的核心闭环：环境感知、工具调用、多轮记忆、执行反馈、可解释决策和可追溯回答。

## 项目最难点回答模板

如果问：

> 你觉得最难的地方是什么？

不要说“调用 OpenAI API”。

可以这样回答：

> 最难的不是生成 SQL，而是如何让生成和回答过程都可控、可验证。LLM 很容易幻觉表名、列名，或者生成语法正确但语义不对的 SQL；即使 SQL 执行成功，LLM 在解释结果时也可能编造数字。所以我做了四件事：第一，用 SchemaScanner 把数据库结构和列级语义结构化；第二，让 Agent 只能通过工具访问数据库，并做 schema 白名单；第三，引入 CandidateRanker，不直接相信第一条 SQL，而是基于执行证据排序；第四，引入 ResultAnalyzer，让最终答案只能基于 SQL result，LLM 输出不 grounded 时自动回退。这样系统从 prompt demo 变成了一个有安全边界、决策证据和答案证据的 Agent。

## 你负责了哪些模块

如果问：

> 你负责了哪些模块？

可以这样回答：

> 我主要负责核心 Agent 链路和可靠性增强，包括：
>
> 1. SchemaScanner 和列级上下文增强。
> 2. AgentToolkit 工具封装和 schema 白名单校验。
> 3. ReAct / Plan-and-Solve Agent 调用链路。
> 4. ConversationManager 多轮上下文接入。
> 5. DAIL/DIN 风格 SQL 自纠错。
> 6. CandidateRanker 候选 SQL 执行验证和证据化排序。
> 7. ResultAnalyzer 基于 SQL result 的稳定回答和 LLM grounded 回退。
> 8. FastAPI `/api/v1/question` 端到端接口和 SQLite + MockLLM 测试。

如果担心“说太多像一个人做完整项目”，可以改成：

> 我主要负责核心 NL-to-SQL Agent 链路中的 Schema 理解、工具调用安全、SQL 自纠错、候选排序和结果分析部分，其他存储和 API 框架参考已有工程结构做了适配。

## 核心拷问问题与回答

### 1. 为什么不用 LangChain 现成 SQL Agent？

回答：

> LangChain 快速搭 demo 很方便，但黑盒程度高，中间步骤、工具调用约束、错误处理和安全控制不够细。这个项目希望验证企业场景下可控的 NL-to-SQL 链路，所以我自己实现了 ReAct loop，把每次 Thought、Action、Observation 都显式记录下来，也能在工具层做 schema 白名单和 SQL 安全拦截。

### 2. 为什么要 SchemaScanner？

回答：

> LLM 不知道数据库真实结构，如果只靠 prompt 容易幻觉表名和列名。SchemaScanner 用 SQLAlchemy inspector 获取真实 schema，包括表、列、主键、外键、样本值、低基数字段、distinct/null 统计和语义类型。Agent 生成 SQL 前先基于真实 schema 工作，能明显降低幻觉。

### 3. Schema Linking 解决什么？

回答：

> 多表查询的难点是 JOIN。模型可以猜 JOIN，但不可靠。我用主外键构建表关系图，当问题涉及多个表时，可以找到表之间的连接路径，辅助 Agent 生成正确 JOIN 条件。

### 4. 多轮对话怎么实现？

回答：

> 我定义了 `Conversation` 和 `ConversationTurn`，保存用户问题、助手 SQL 和 SQL 执行结果。API 层通过全局 `System` 和存储化 `ConversationManager` 复用会话，同一个 `conversation_id` 可以跨请求恢复历史。后续问题可以把最近几轮历史注入 prompt，用来处理“那只看前三个”这种省略表达。

### 5. SQL 生成错了怎么办？

回答：

> 有三层处理。第一层是工具层执行前校验，过滤危险 SQL 和未知表列。第二层是 DAIL 风格自纠错，执行 SQL 后把数据库错误或样本反馈交给 LLM 修正。第三层是候选 SQL 排序，不只看一条 SQL，而是对候选做执行验证和评分，选择证据最好的结果。

### 6. CandidateRanker 为什么是亮点？

回答：

> 普通 NL-to-SQL 往往直接返回 LLM 第一条 SQL，但 LLM 可能格式对、语义错。我加入 CandidateRanker，把候选 SQL 逐个做 schema 校验、危险命令拦截、真实执行、证据收集，然后基于执行结果、问题意图和 Evaluator 分数排序。API 会返回 `candidates`，所以系统选择过程是透明的；同时最优候选的执行结果会进入 `result`，成为最终 `answer` 和 `analysis` 的证据源。

### 7. 为什么不只返回 SQL？

回答：

> 从业务需求看，用户要的是问题答案，不是 SQL 字符串。只返回 SQL 对开发者有用，但对业务用户还不够完整，所以我把最优候选 SQL 的执行结果透出到 API，再由 ResultAnalyzer 生成 answer、summary 和 key findings。这里有一个关键边界：SQL 一定由系统执行，LLM 只能基于受控结果做表达；如果 LLM 分析结果时缺少 evidence 或编造 SQL result 中不存在的数字，就回退到启发式分析。

### 8. 怎么保证安全？

回答：

> 当前有几层安全边界：
>
> 第一，LLM 不直接连接数据库，只能调用 `AgentToolkit`。
>
> 第二，SQL 执行层拦截 `DROP/DELETE/UPDATE/ALTER/TRUNCATE` 等危险命令。
>
> 第三，工具层对表名、列名做 schema 白名单。
>
> 第四，CandidateRanker 执行候选前再次校验表名。
>
> 第五，LLMResultAnalyzer 只消费 SQL result，不接触数据库连接；输出必须带 evidence，不可信时回退到启发式分析。
>
> 生产环境还可以继续加只读数据库账号、SQL AST 审计、行列级权限控制和查询超时。

### 9. 这个项目有哪些不足？

回答：

> 当前是 PoC / 原型，不是完整生产系统。主要不足有：
>
> 1. 复杂 SQL 的 alias、CTE、子查询列级白名单还比较保守。
> 2. 候选 SQL 目前主要来自主输出和中间步骤，还没做多策略主动生成。
> 3. LLM 结果分析当前主要校验 evidence 和数值可追溯性，复杂因果解释还需要更严格的结论类型约束。
> 4. 真实 OpenAI、MongoDB、ChromaDB 集成测试需要凭据环境才能跑。
> 5. 还没有接 Langfuse 这类 Agent trace 系统。
> 6. 权限控制还停留在 schema 白名单和危险命令拦截，生产化还需要更细粒度审计。

### 10. `sql_metadata` 不存在怎么办？

回答：

> 工具层和 ranker 都有 fallback，用正则解析 FROM/JOIN 表名。这个 fallback 主要保证简单 SQL 不被可选依赖阻断。复杂 SQL 有 alias、CTE、子查询和函数表达式，后续生产化应该引入 SQL AST parser。

### 11. 为什么不用正则直接解析所有 SQL？

回答：

> 简单 fallback 可以，但复杂 SQL 有 alias、CTE、子查询、函数表达式，正则不可靠。生产化应该用 SQL AST，把表、alias、列引用、子查询作用域都解析出来。

### 12. 为什么 CandidateRanker 里 `COUNT` 会加分？

回答：

> 这是问题意图启发式。如果问题出现“多少、数量、count、how many”，聚合计数更符合语义。它不是唯一依据，还要结合执行成功、schema 校验和 Evaluator 分数。

### 13. 如果 SQL 执行成功但语义错怎么办？

回答：

> 执行成功只能证明语法和数据访问没问题，不能完全证明语义正确。所以还需要问题意图评分、LLM Evaluator、few-shot、执行结果解释，以及后续更强的测试集评估。当前 ResultAnalyzer 解决的是“基于已选 SQL 的结果不要被解释歪”，不是替代 SQL 语义正确性评估。

### 14. 怎么评估 NL-to-SQL 准确率？

回答：

> 可以从几个指标评估：
>
> - execution accuracy：生成 SQL 执行结果是否和 golden SQL 一致。
> - exact match：SQL 字符串是否匹配，但参考价值较低。
> - valid rate：SQL 能否执行。
> - repair success rate：自纠错后成功率。
> - latency 和 token cost。
> - 安全拦截率和误杀率。

### 15. 为什么要 IoC？

回答：

> IoC 方便替换 OpenAI、Azure、本地模型，也方便替换 MongoDB/内存存储、Chroma/其他向量库。业务代码依赖接口而不是具体 SDK，测试时可以用 MockLLM 和 MemoryStorage 稳定复现。

### 16. 这个项目上线需要做什么？

回答：

> 如果上线到真实企业数据库，需要补：
>
> 1. 只读数据库账号。
> 2. SQL AST 权限审计。
> 3. 查询超时和行数限制。
> 4. Agent trace。
> 5. 用户权限和库表权限。
> 6. 真实评测集。
> 7. 缓存和限流。
> 8. 敏感字段脱敏。
> 9. 多租户隔离。

## 简历描述

可以直接放简历：

> 基于 Dataherald 架构重构 NL-to-SQL / NL-to-data-answer Agent 原型，实现原生 ReAct 和 Plan-and-Solve 双 Agent 路由、Schema Scanner/Linking、多轮会话记忆、DIN/DAIL 风格执行反馈自纠错，并进一步加入多候选 SQL 执行验证、证据化排序和 grounded 结果分析机制。系统通过 IoC 支持 LLM、存储、向量库和评估器替换，提供 FastAPI 接口，使用 SQLite + MockLLM 完成端到端测试，核心模块测试 90 passed。

如果要贴近实习经历：

> 在神州数码实习期间，参与企业数据库问答 Data Agent 原型建设，负责核心 NL-to-SQL / NL-to-data-answer 链路中的 Schema 理解、Agent 工具调用、安全校验、SQL 自纠错、候选 SQL 证据化排序和结果 grounded 分析。通过 SQLAlchemy 扫描数据库结构与列级语义，结合 ReAct/Plan-and-Solve Agent 生成 SQL，并基于执行反馈、候选排序和 SQL result evidence 提升结果可靠性。

## 面试时主动展示什么

重点展示 `/api/v1/question` 返回中的 `answer`、`result`、`analysis` 和 `candidates` 字段：

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

这个返回能体现：

- Agent 不是黑盒。
- SQL 选择有执行证据。
- 系统能解释为什么选这条 SQL。
- 最终答案绑定到 SQL result evidence，不是 LLM 自由发挥。

## 最后要记住

你准备这个项目时，不要把重点放在“我会调用大模型 API”。真正有含金量的是：

- 你知道 LLM 会幻觉。
- 你知道企业数据库查询需要安全边界。
- 你知道 NL-to-SQL 不能只看语法，要看执行结果、语义和最终答案是否 grounded。
- 你知道如何用测试保证核心链路稳定。
- 你能承认原型边界，并给出生产化演进方案。

核心收束句：

> 我做的不是一个 prompt demo，而是围绕 NL-to-SQL 的不确定性，设计了一套 schema 感知、工具约束、执行反馈、自纠错、候选证据排序和 grounded 结果分析的工程闭环。
