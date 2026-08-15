# Eval Cases

本目录存放 Data Agent 离线评估用例和语义模型。

## 当前文件

- `demo_semantic.yml`：最小语义评估样例。
- `business_semantic_model.yml`：业务 benchmark 使用的 Semantic Layer，定义 GMV、净收入、订单数、退款金额、毛利等指标，以及月份、区域、客户分层、产品类别、渠道等维度。
- `business_benchmark.yml`：40 条业务问题 benchmark，覆盖 basic、semantic、join、trend、analysis、visualization 和 safety 标签。

## SQLite 业务数据集

`sql_agent/eval/demo_business.py` 提供 `BusinessDemoBuilder`，会构造一个确定性的 SQLite 数据库，包含以下表：

- `departments`
- `employees`
- `customers`
- `products`
- `orders`
- `order_items`
- `refunds`
- `web_events`

前 10 条 benchmark case 带 `golden_sql`，可以直接在该 SQLite 数据库上执行，用于验证原型阶段的业务 SQL 口径和评估链路。

## 推荐验证命令

```bash
pytest tests/test_business_benchmark_dataset.py -q
pytest tests/test_eval_benchmark_2.py -q
```
