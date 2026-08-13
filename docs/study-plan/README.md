# SQL Agent 两周吃透学习资料包

这个目录用于把“两周吃透 SQL Agent 项目学习计划”落地成可执行资料。目标不是泛泛读代码，而是围绕面试深挖建立四类能力：

- 能画清楚系统链路：用户问题如何经过 API、Semantic Layer、Context、Schema、Agent、Tools、Correction、CandidateRanker、ResultAnalyzer 和 Visualization 最终变成可追溯数据答案。
- 能讲清楚技术选型：FastAPI、Pydantic、SQLAlchemy、OpenAI SDK、MongoDB、ChromaDB、pytest 分别解决什么问题。
- 能解释源码细节：核心类、核心函数、数据流、错误处理、测试策略。
- 能经受追问：能坦诚说明项目边界、风险、改进方向，而不是只背 README。
- 能解释 2.0 深化能力：Semantic Layer 业务语义治理、verified query 学习、候选 SQL 可解释排序、grounded 洞察、ECharts 可视化资产和 Evaluation Benchmark。

## 使用方式

建议每天学习 3-4 小时，按下面顺序推进：

1. 打开 [`14-day-learning-plan.md`](./14-day-learning-plan.md)，按当天任务读代码、跑测试、写笔记。
2. 使用 [`daily-notes-template.md`](./daily-notes-template.md) 记录当天输出。
3. 每学完一个模块，补充 [`technical-cheatsheet.md`](./technical-cheatsheet.md) 中对应部分。
4. 第 13-14 天重点使用 [`interview-playbook.md`](./interview-playbook.md) 做模拟面试。
5. 遇到链路不清楚时，回到 [`diagrams.md`](./diagrams.md) 重新画图。

## 推荐目录结构

```text
docs/study-plan/
├── README.md                 # 本说明
├── 14-day-learning-plan.md   # 14 天执行手册
├── daily-notes-template.md   # 每日笔记模板
├── technical-cheatsheet.md   # 技术细节速查表
├── interview-playbook.md     # 面试答辩稿和追问答案
└── diagrams.md               # 核心流程图和白板图
```

## 每日固定动作

每天不要只读代码，要完成这四步：

1. **读**：读当天指定源码和测试。
2. **跑**：运行当天指定 pytest 命令。
3. **画**：画一个链路图、类关系图或数据流图。
4. **讲**：用 2-5 分钟口述当天模块，录音或自测。

## 最终验收

第 14 天结束时，你应能做到：

- 5 分钟讲清项目背景、架构、亮点、难点和不足。
- 白板画出主链路、ReAct 循环、Schema Linking、自纠错闭环。
- 白板画出 SemanticQueryPlan、CandidateRanker 决策、ResultAnalyzer grounding、Visualization asset 和 Evaluation Benchmark 闭环。
- 解释 `sql_agent` 每个核心包的职责。
- 回答至少 20 个围绕项目的深入追问。
- 说清楚测试体系为什么可信、哪里还不够。

当前项目基线：

```text
pytest -q tests
119 passed, 3 skipped, 2 warnings
```

3 个 skipped 是真实 OpenAI、MongoDB、ChromaDB 集成测试，默认需要显式配置真实环境才运行。
