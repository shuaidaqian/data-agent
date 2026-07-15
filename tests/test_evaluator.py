import pytest
from sql_agent.eval.evaluator import SimpleEvaluator
from sql_agent.core.config import Settings, System

class TestSimpleEvaluator:
    @pytest.fixture
    def evaluator(self):
        return SimpleEvaluator(System(Settings()))

    def test_valid_sql(self, evaluator):
        score = evaluator.evaluate("SELECT * FROM employees", "Show employees")
        assert score >= 0.5

    def test_invalid_sql(self, evaluator):
        score = evaluator.evaluate("invalid sql", "Show")
        assert score < 0.5

    def test_no_select(self, evaluator):
        score = evaluator.evaluate("DROP TABLE t", "Drop")
        assert score < 0.5

    def test_no_from(self, evaluator):
        score = evaluator.evaluate("SELECT 1", "Just 1")
        assert score < 0.5

    def test_score_range(self, evaluator):
        score = evaluator.evaluate("SELECT name FROM employees WHERE id = 1", "Get name")
        assert 0.0 <= score <= 1.0
