"""业务 benchmark 使用的确定性 SQLite 数据集。"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class BusinessDemoBuilder:
    """构造面向 NL-to-SQL 评估的轻量业务数据库。"""

    def __init__(self, output_dir: str | Path, db_name: str = "business_demo.sqlite"):
        self.output_dir = Path(output_dir)
        self.db_name = db_name

    def build(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.output_dir / self.db_name
        if db_path.exists():
            db_path.unlink()

        with sqlite3.connect(db_path) as conn:
            self._create_schema(conn)
            self._insert_seed_data(conn)
            conn.commit()
        return db_path

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE departments (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL
            );

            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                salary REAL NOT NULL,
                hire_date TEXT NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );

            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                segment TEXT NOT NULL,
                signup_date TEXT NOT NULL,
                acquisition_channel TEXT NOT NULL
            );

            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                list_price REAL NOT NULL,
                cost REAL NOT NULL
            );

            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                channel TEXT NOT NULL,
                discount_amount REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE refunds (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                refund_date TEXT NOT NULL,
                amount REAL NOT NULL,
                reason TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            );

            CREATE TABLE web_events (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                event_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                channel TEXT NOT NULL,
                session_id TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            """
        )

    def _insert_seed_data(self, conn: sqlite3.Connection) -> None:
        conn.executemany(
            "INSERT INTO departments VALUES (?, ?, ?)",
            [
                (1, "销售部", "北京"),
                (2, "客户成功部", "上海"),
                (3, "产品部", "深圳"),
                (4, "运营部", "广州"),
            ],
        )
        conn.executemany(
            "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "张伟", 1, "销售经理", 32000, "2021-03-15"),
                (2, "李娜", 1, "销售顾问", 22000, "2022-05-20"),
                (3, "王强", 2, "客户成功经理", 26000, "2020-11-01"),
                (4, "赵敏", 4, "运营分析师", 24000, "2023-01-10"),
                (5, "陈晨", 3, "产品经理", 30000, "2021-09-08"),
            ],
        )
        conn.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "华北零售", "华北", "企业", "2023-01-05", "官网"),
                (2, "长三角制造", "华东", "企业", "2023-02-11", "展会"),
                (3, "岭南贸易", "华南", "中小企业", "2023-03-17", "渠道"),
                (4, "西部能源", "西南", "企业", "2023-05-02", "官网"),
                (5, "华东电商", "华东", "中小企业", "2024-01-18", "广告"),
                (6, "北方物流", "华北", "中小企业", "2024-02-22", "渠道"),
            ],
        )
        conn.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
            [
                (1, "数据治理平台", "软件", 120000, 42000),
                (2, "BI 分析套件", "软件", 80000, 26000),
                (3, "实施服务", "服务", 50000, 22000),
                (4, "运维服务", "服务", 30000, 12000),
                (5, "培训服务", "服务", 15000, 5000),
            ],
        )
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 1, "2024-01-12", "paid", "direct", 5000),
                (2, 2, 2, "2024-01-20", "paid", "partner", 0),
                (3, 3, 2, "2024-02-03", "paid", "direct", 3000),
                (4, 4, 1, "2024-02-18", "cancelled", "direct", 0),
                (5, 5, 3, "2024-03-05", "paid", "online", 2000),
                (6, 6, 2, "2024-03-21", "paid", "partner", 4000),
                (7, 1, 1, "2024-04-02", "paid", "direct", 0),
                (8, 2, 3, "2024-04-15", "refunded", "online", 1000),
                (9, 5, 4, "2024-05-09", "paid", "online", 0),
                (10, 3, 2, "2024-05-22", "paid", "partner", 2500),
                (11, 4, 1, "2024-06-11", "paid", "direct", 6000),
                (12, 6, 4, "2024-06-27", "paid", "online", 1500),
            ],
        )
        conn.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 1, 1, 120000),
                (2, 1, 3, 1, 50000),
                (3, 2, 2, 1, 80000),
                (4, 2, 5, 2, 15000),
                (5, 3, 3, 2, 50000),
                (6, 4, 1, 1, 120000),
                (7, 5, 2, 1, 80000),
                (8, 5, 4, 1, 30000),
                (9, 6, 1, 1, 120000),
                (10, 6, 5, 1, 15000),
                (11, 7, 4, 2, 30000),
                (12, 8, 2, 1, 80000),
                (13, 8, 3, 1, 50000),
                (14, 9, 5, 3, 15000),
                (15, 10, 1, 1, 120000),
                (16, 10, 4, 1, 30000),
                (17, 11, 2, 2, 80000),
                (18, 11, 3, 1, 50000),
                (19, 12, 4, 1, 30000),
                (20, 12, 5, 2, 15000),
            ],
        )
        conn.executemany(
            "INSERT INTO refunds VALUES (?, ?, ?, ?, ?)",
            [
                (1, 8, "2024-04-20", 60000, "客户预算变更"),
                (2, 3, "2024-02-15", 10000, "交付范围调整"),
                (3, 12, "2024-07-03", 5000, "服务时长调整"),
            ],
        )
        conn.executemany(
            "INSERT INTO web_events VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, 1, "2024-01-01", "visit", "organic", "s001"),
                (2, 1, "2024-01-02", "demo_request", "organic", "s001"),
                (3, 2, "2024-01-09", "visit", "event", "s002"),
                (4, 2, "2024-01-10", "trial_start", "event", "s002"),
                (5, 3, "2024-02-01", "visit", "partner", "s003"),
                (6, 5, "2024-03-01", "visit", "paid", "s004"),
                (7, 5, "2024-03-02", "demo_request", "paid", "s004"),
                (8, 6, "2024-03-12", "visit", "partner", "s005"),
                (9, 4, "2024-05-20", "visit", "organic", "s006"),
                (10, 4, "2024-05-21", "trial_start", "organic", "s006"),
            ],
        )
