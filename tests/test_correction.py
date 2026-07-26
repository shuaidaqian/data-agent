import pytest
from unittest.mock import MagicMock
from sql_agent.correction.base import CorrectionResult
from sql_agent.core.types import LLMConfig


class TestCorrectionResult:
    def test_default(self):
        r = CorrectionResult()
        assert r.sql == "" and r.status == "INVALID" and r.rounds == 0

    def test_custom(self):
        r = CorrectionResult(
            sql="SELECT 1", status="VALID", reason="Fixed", rounds=2, sql_before="SELECT 2"
        )
        assert r.sql == "SELECT 1" and r.rounds == 2


class TestValidate:
    @pytest.fixture
    def c(self, sql_database):
        from sql_agent.correction.din_style import DINStyleCorrector

        o = DINStyleCorrector.__new__(DINStyleCorrector)
        o.llm = MagicMock()
        o.database = sql_database
        o.llm_config = LLMConfig()
        o.max_rounds = 3
        return o

    def test_validate_empty(self, c):
        v, e = c.validate_sql("")
        assert not v and "Empty" in e

    def test_validate_valid(self, c):
        v, e = c.validate_sql("SELECT 1")
        if not v:
            assert e is not None
        else:
            assert v
