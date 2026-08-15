import pytest
from sql_agent.sql.database import SQLInjectionError


class TestSQLDatabase:
    def test_run_simple(self, sql_database):
        _, result = sql_database.run_sql("SELECT COUNT(*) as cnt FROM employees")
        assert result["result"][0]["cnt"] == 4

    def test_run_top_k(self, sql_database):
        _, result = sql_database.run_sql("SELECT * FROM employees", top_k=2)
        assert len(result["result"]) == 2

    def test_join(self, sql_database):
        _, result = sql_database.run_sql(
            "SELECT e.name, d.name as dept FROM employees e JOIN departments d ON e.department_id = d.id"
        )
        assert result["row_count"] == 4

    def test_aggregation(self, sql_database):
        _, result = sql_database.run_sql(
            "SELECT d.name, AVG(e.salary) FROM employees e JOIN departments d ON e.department_id = d.id GROUP BY d.name"
        )
        assert result["row_count"] == 3

    def test_get_tables(self, sql_database):
        tables = sql_database.get_tables_and_views()
        assert any("employees" in t for t in tables)
        assert any("departments" in t for t in tables)

    def test_dialect_name_is_sqlglot_compatible(self, sql_database):
        assert sql_database.dialect == "sqlite"

    def test_sql_injection_drop(self, sql_database):
        with pytest.raises(SQLInjectionError):
            sql_database.run_sql("DROP TABLE employees")

    def test_sql_injection_delete(self, sql_database):
        with pytest.raises(SQLInjectionError):
            sql_database.run_sql("DELETE FROM employees")

    def test_sql_injection_update(self, sql_database):
        with pytest.raises(SQLInjectionError):
            sql_database.run_sql("UPDATE employees SET salary = 100000")

    def test_get_ddl(self, sql_database):
        ddl = sql_database.get_table_ddl("employees")
        assert "CREATE TABLE" in ddl
        assert "PRIMARY KEY" in ddl
