# SQL Agent 核心图谱

## 1. NL->Data Answer 主链路

```mermaid
flowchart TD
    A["用户自然语言问题"] --> B["FastAPI /api/v1/question"]
    B --> C["QuestionRequest"]
    C --> D["Prompt + Conversation"]
    D --> E["加载 DatabaseConnection"]
    E --> F["SQLDatabase"]
    F --> G["SchemaScanner 扫描表结构"]
    D --> S["SemanticPlanner 生成 SemanticQueryPlan"]
    S --> S1["SemanticSQLCompiler 编译 semantic SQL"]
    D --> H["ContextRetriever 检索上下文"]
    H --> H1["Golden SQL few-shot"]
    H --> H2["管理员指令"]
    D --> V["FeedbackService 召回 verified query"]
    G --> I["AgentSelector 判断复杂度"]
    H1 --> I
    H2 --> I
    I --> J["ReActAgent"]
    I --> K["PlanSolveAgent"]
    J --> L["AgentToolkit 工具调用"]
    K --> L
    L --> M["生成 SQL"]
    M --> N["DAIL / DIN 自纠错"]
    S1 --> R["CandidateRanker"]
    V --> R
    N --> R
    R --> R1["执行验证 + 评分拆解 + 结果形状校验"]
    R1 --> A1["ResultAnalyzer grounded 洞察"]
    A1 --> Z["VisualizationRecommender ECharts option"]
    Z --> O["SQLResponse: answer + sql + result + analysis + visualization + candidates"]
```

## 2. ReAct 循环

```mermaid
flowchart LR
    A["Question + Context + Tools"] --> B["Thought"]
    B --> C["Action"]
    C --> D["Tool Execution"]
    D --> E["Observation"]
    E --> B
    B --> F["Final SQL"]
```

## 3. Plan-and-Solve 流程

```mermaid
flowchart TD
    A["复杂自然语言问题"] --> B["Plan Phase"]
    B --> C["识别表"]
    B --> D["识别 JOIN"]
    B --> E["识别过滤"]
    B --> F["识别聚合和排序"]
    C --> G["Execute Phase"]
    D --> G
    E --> G
    F --> G
    G --> H["工具调用验证"]
    H --> I["Final SQL"]
```

## 4. Schema Linking 外键图

```mermaid
flowchart LR
    S["sales"] -->|employee_id = employees.id| E["employees"]
    E -->|department_id = departments.id| D["departments"]
    S -->|product_id = products.id| P["products"]
```

## 5. 自纠错闭环

```mermaid
flowchart TD
    A["生成 SQL"] --> B["执行 SQL"]
    B --> C{"执行成功?"}
    C -->|否| D["收集数据库错误"]
    C -->|是| E["检查样本结果和语义一致性"]
    D --> F["LLM 根据反馈修正"]
    E --> G{"语义一致?"}
    G -->|否| F
    G -->|是| H["返回有效 SQL"]
    F --> B
```

## 6. 测试金字塔

```mermaid
flowchart TD
    A["真实集成测试 OpenAI/Mongo/Chroma"] --> B["API 端到端测试 MockLLM + Fake Storage"]
    B --> C["模块集成测试 SQL/JOIN/Schema/Conversation"]
    C --> D["单元测试 数据模型/工具/纠错/评估"]
```

## 7. SemanticQueryPlan 编译链路

```mermaid
flowchart TD
    A["自然语言问题"] --> B["Metric / Dimension 同义词匹配"]
    B --> C{"多个指标歧义?"}
    C -->|是| D["NEEDS_CLARIFICATION + clarification_options"]
    C -->|否| E["SemanticQueryPlan"]
    E --> F["metrics / dimensions / filters / time_grain / limit"]
    F --> G["SemanticPlanValidator"]
    G --> H["SemanticSQLCompiler"]
    H --> I["SQL 候选"]
```

## 8. CandidateRanker 可解释决策

```mermaid
flowchart TD
    A["候选 SQL 集合"] --> B["去重"]
    B --> C["schema 白名单校验"]
    C --> D["真实执行 SQL"]
    D --> E["收集 row_count / columns / preview / error"]
    E --> F["结果形状校验"]
    F --> G["评分拆解 score_breakdown"]
    G --> H["verified bonus / semantic plan match bonus"]
    H --> I["selection_reason"]
    I --> J["排序后的 candidates"]
```

## 9. Grounded Result Analysis

```mermaid
flowchart TD
    A["最优 SQLCandidate.execution"] --> B["QueryResultPayload"]
    B --> C{"结果形状"}
    C -->|单行单列| D["single_metric finding"]
    C -->|多行数值| E["Top K / max-min / share finding"]
    C -->|空结果| F["empty result limitation"]
    D --> G["answer / summary / key_findings"]
    E --> G
    F --> G
    G --> H["每个 finding 绑定 SQL result evidence"]
    H --> I["why 问题追加因果限制"]
```

## 10. Visualization 2.0

```mermaid
flowchart TD
    A["QueryResultPayload + key_findings"] --> B{"结果结构"}
    B -->|单行单列| C["metric_card"]
    B -->|分类 + 数值| D["bar"]
    B -->|时间 + 数值| E["line"]
    B -->|占比/份额| F["pie"]
    B -->|其他| G["table"]
    C --> H["ECharts option"]
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I["ChartValidation: x/y 存在、y 数值、时间字段校验"]
```

## 11. Feedback + Evaluation Loop

```mermaid
flowchart TD
    A["用户反馈"] --> B["WrongReason enum"]
    B --> C["corrected_sql?"]
    C -->|是| D["VerifiedQuery PENDING_REVIEW"]
    D --> E["quality_signals"]
    E --> F["后续问题召回 verified query"]
    F --> G["CandidateRanker 加分但仍执行验证"]
    A --> H["semantic update suggestion"]
    I["Benchmark cases"] --> J["API case runner / harness"]
    J --> K["tag_metrics"]
    J --> L["error_breakdown"]
    K --> M["迭代质量复盘"]
    L --> M
```

## 12. IoC 组件实例化

```mermaid
flowchart TD
    A["System.instance(BaseType)"] --> B["获取 BaseType FQN"]
    B --> C["查组件注册表"]
    C --> D["读取环境变量自定义实现"]
    D --> E{"有自定义实现?"}
    E -->|是| F["import 自定义类"]
    E -->|否| G["使用默认实现"]
    F --> H["校验 issubclass"]
    G --> H
    H --> I["创建实例并缓存"]
    I --> J["返回组件"]
```
