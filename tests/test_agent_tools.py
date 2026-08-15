import pytest
from unittest.mock import MagicMock
from sql_agent.agent.tools import AgentToolkit


class TestAgentToolkit:
    @pytest.fixture
    def toolkit(self, sql_database, sample_table_descriptions):
        mock_llm = MagicMock()
        mock_llm.embed.return_value = [[0.5] * 10]
        return AgentToolkit(
            database=sql_database,
            db_scan=sample_table_descriptions,
            llm_backend=mock_llm,
            few_shot_examples=[{"prompt_text": "Show employees", "sql": "SELECT * FROM employees"}],
            instructions=[{"instruction": "Use table aliases"}],
        )

    def test_tools_count(self, toolkit):
        assert len(toolkit.get_tools()) >= 6

    def test_execute_query(self, toolkit):
        r = toolkit._execute_query("SELECT COUNT(*) as cnt FROM employees")
        assert r.success
        assert "4" in r.output

    def test_system_time(self, toolkit):
        r = toolkit._get_system_time()
        assert r.success
        assert "Time" in r.output or "Date" in r.output

    def test_get_schema(self, toolkit):
        r = toolkit._get_table_schema("employees")
        assert r.success
        assert "employees" in r.output

    def test_get_few_shot(self, toolkit):
        r = toolkit._get_few_shot_examples("1")
        assert r.success
        assert "SELECT" in r.output

    def test_get_instructions(self, toolkit):
        r = toolkit._get_instructions()
        assert r.success
        assert "aliases" in r.output

    def test_invalid_few_shot(self, toolkit):
        r = toolkit._get_few_shot_examples("abc")
        assert not r.success

    def test_column_info(self, toolkit):
        r = toolkit._get_column_info("employees -> name")
        assert r.success

    def test_get_schema_rejects_unknown_table(self, toolkit):
        r = toolkit._get_table_schema("payroll")
        assert not r.success
        assert "不在允许的 schema 白名单" in r.output

    def test_column_info_rejects_unknown_column(self, toolkit):
        r = toolkit._get_column_info("employees -> secret_salary")
        assert not r.success
        assert "不在允许的 schema 白名单" in r.output

    def test_entity_checker_rejects_unknown_table(self, toolkit):
        r = toolkit._check_entity("payroll -> name, Alice")
        assert not r.success
        assert "不在允许的 schema 白名单" in r.output

    def test_execute_query_rejects_unknown_column_by_ast_safety(self, toolkit):
        r = toolkit._execute_query("SELECT secret_salary FROM employees")

        assert not r.success
        assert "SQL AST 安全校验失败" in r.output
        assert "secret_salary" in r.output

    def test_execute_query_rejects_dangerous_statement_by_ast_safety(self, toolkit):
        r = toolkit._execute_query("DELETE FROM employees")

        assert not r.success
        assert "SQL AST 安全校验失败" in r.output
