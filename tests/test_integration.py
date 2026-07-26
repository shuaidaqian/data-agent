import pytest


class TestIntegration:
    def test_join_query(self, sql_database):
        _, r = sql_database.run_sql(
            "SELECT d.name, COUNT(e.id) as cnt FROM departments d "
            "LEFT JOIN employees e ON d.id = e.department_id "
            "GROUP BY d.name ORDER BY cnt DESC"
        )
        assert len(r["result"]) == 3
        assert r["result"][0]["cnt"] == 2

    def test_aggregation(self, sql_database):
        _, r = sql_database.run_sql("SELECT AVG(salary) as avg_sal FROM employees")
        assert r["result"][0]["avg_sal"] == pytest.approx(72500, abs=1)

    def test_subquery(self, sql_database):
        _, r = sql_database.run_sql(
            "SELECT name FROM employees WHERE salary > (SELECT AVG(salary) FROM employees)"
        )
        names = [row["name"] for row in r["result"]]
        assert "Alice" in names
        assert "Charlie" in names

    def test_three_table_join(self, sql_database):
        _, r = sql_database.run_sql(
            "SELECT e.name, p.name as product, s.quantity "
            "FROM sales s JOIN employees e ON s.employee_id = e.id "
            "JOIN products p ON s.product_id = p.id "
            "ORDER BY s.quantity DESC"
        )
        assert len(r["result"]) == 5

    def test_date_filter(self, sql_database):
        _, r = sql_database.run_sql("SELECT * FROM sales WHERE sale_date >= '2023-02-01'")
        assert len(r["result"]) == 3

    def test_schema_linking_join(self, sample_table_descriptions):
        from sql_agent.sql.schema_linking import SchemaLinker

        linker = SchemaLinker(sample_table_descriptions)
        paths = linker.find_join_paths(["employees", "departments", "sales"])
        assert len(paths) >= 2

    def test_conversation_pipeline(self):
        from sql_agent.context.conversation import ConversationManager

        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        mgr.add_turn(conv, "user", "Show departments")
        mgr.add_turn(
            conv, "assistant", "SELECT * FROM departments", sql="SELECT * FROM departments"
        )
        ctx = mgr.build_context_prompt(conv, "Show employees")
        assert "departments" in ctx
