import pytest
from sql_agent.agent.base import AgentResult, StepResult
from sql_agent.core.types import Prompt
from sql_agent.core.config import Settings, System


class TestAgentBase:
    @pytest.fixture
    def agent(self):
        from sql_agent.agent.base import SQLAgent
        class T(SQLAgent):
            def generate_sql(self, **kwargs):
                return AgentResult(sql='SELECT 1')
            def stream_sql(self, **kwargs):
                yield {'type': 'result', 'content': AgentResult(sql='SELECT 1')}
        return T(System(Settings()))

    def test_extract_sql(self, agent):
        sql = agent.extract_sql_from_output("Here is the SQL:\n```sql\n```\nSELECT * FROM t\n```")
        assert sql == 'SELECT * FROM t'

    def test_extract_sql_none(self, agent):
        assert agent.extract_sql_from_output('No SQL') is None

    def test_truncate_short(self, agent):
        assert agent.truncate_observation('hello', 100) == 'hello'

    def test_truncate_long(self, agent):
        o = agent.truncate_observation('x' * 100, 10)
        assert '(truncated)' in o

    def test_complexity_simple(self, agent):
        p = Prompt(text='Show all employees', db_connection_id='db1')
        assert agent.estimate_complexity(p, []) in ('simple', 'medium')

    def test_complexity_complex(self, agent):
        p = Prompt(text='Compare avg salary month over month and rank', db_connection_id='db1')
        assert agent.estimate_complexity(p, []) == 'complex'

    def test_complexity_medium(self, agent):
        p = Prompt(text='Top 5 products by sales', db_connection_id='db1')
        assert agent.estimate_complexity(p, []) in ('medium', 'complex')


class TestStepResult:
    def test_create(self):
        s = StepResult(thought='Think', action='Tool', action_input='input', observation='obs')
        assert s.action == 'Tool'


class TestAgentResult:
    def test_default(self):
        r = AgentResult()
        assert r.sql == '' and r.status == 'PENDING' and r.steps == []

    def test_with_values(self):
        r = AgentResult(sql='SELECT 1', status='VALID', tokens_used=100)
        assert r.tokens_used == 100
