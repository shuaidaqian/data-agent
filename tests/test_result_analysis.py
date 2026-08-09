from sql_agent.analysis.result_analyzer import HeuristicResultAnalyzer
from sql_agent.analysis.result_analyzer import LLMResultAnalyzer
from sql_agent.ranking.candidate import CandidateExecution, SQLCandidate


def test_result_analyzer_builds_grounded_answer_for_single_metric():
    analyzer = HeuristicResultAnalyzer()
    candidate = SQLCandidate(
        sql="SELECT COUNT(*) AS cnt FROM employees",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=1,
            columns=["cnt"],
            preview=[{"cnt": 4}],
        ),
    )

    analysis = analyzer.analyze("员工数量是多少？", candidate)

    assert analysis.answer == "当前查询结果为 4。"
    assert analysis.result.columns == ["cnt"]
    assert analysis.result.rows == [{"cnt": 4}]
    assert analysis.key_findings[0].claim == "cnt = 4"
    assert analysis.key_findings[0].evidence == "SQL result: cnt = 4"
    assert "当前数据库快照" in analysis.limitations[0]


def test_result_analyzer_reports_empty_result_without_fabrication():
    analyzer = HeuristicResultAnalyzer()
    candidate = SQLCandidate(
        sql="SELECT * FROM employees WHERE name = '不存在'",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=0,
            columns=["id", "name"],
            preview=[],
        ),
    )

    analysis = analyzer.analyze("查询不存在的员工", candidate)

    assert "没有返回数据" in analysis.answer
    assert analysis.key_findings == []
    assert any("筛选条件" in item for item in analysis.limitations)


class FakeAnalysisLLM:
    def __init__(self, response: str):
        self.response = response
        self.messages = None

    def generate(self, messages, config=None, **kwargs):
        self.messages = messages
        return self.response


def test_llm_result_analyzer_accepts_only_grounded_json_findings():
    llm = FakeAnalysisLLM(
        """
        {
          "answer": "当前员工总数为 4 人。",
          "summary": "查询返回 cnt = 4。",
          "key_findings": [
            {"claim": "员工总数为 4 人。", "evidence": "SQL result: cnt = 4"}
          ],
          "limitations": ["该结论仅基于当前数据库快照。"],
          "followup_questions": ["是否需要按部门统计？"]
        }
        """
    )
    candidate = SQLCandidate(
        sql="SELECT COUNT(*) AS cnt FROM employees",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=1,
            columns=["cnt"],
            preview=[{"cnt": 4}],
        ),
    )

    analysis = LLMResultAnalyzer(llm).analyze("员工数量是多少？", candidate)

    assert analysis.answer == "当前员工总数为 4 人。"
    assert analysis.key_findings[0].evidence == "SQL result: cnt = 4"
    assert "只能根据给定 SQL 执行结果" in llm.messages[0]["content"]


def test_llm_result_analyzer_falls_back_when_finding_lacks_evidence():
    llm = FakeAnalysisLLM(
        """
        {
          "answer": "员工很多。",
          "summary": "模型自由发挥。",
          "key_findings": [
            {"claim": "员工很多。", "evidence": ""}
          ],
          "limitations": [],
          "followup_questions": []
        }
        """
    )
    candidate = SQLCandidate(
        sql="SELECT COUNT(*) AS cnt FROM employees",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=1,
            columns=["cnt"],
            preview=[{"cnt": 4}],
        ),
    )

    analysis = LLMResultAnalyzer(llm).analyze("员工数量是多少？", candidate)

    assert analysis.answer == "当前查询结果为 4。"
    assert analysis.key_findings[0].evidence == "SQL result: cnt = 4"


def test_llm_result_analyzer_falls_back_when_answer_contains_ungrounded_number():
    llm = FakeAnalysisLLM(
        """
        {
          "answer": "当前员工总数为 999 人。",
          "summary": "查询显示员工总数为 999。",
          "key_findings": [
            {"claim": "cnt = 4", "evidence": "SQL result: cnt = 4"}
          ],
          "limitations": [],
          "followup_questions": []
        }
        """
    )
    candidate = SQLCandidate(
        sql="SELECT COUNT(*) AS cnt FROM employees",
        status="VALID",
        execution=CandidateExecution(
            success=True,
            row_count=1,
            columns=["cnt"],
            preview=[{"cnt": 4}],
        ),
    )

    analysis = LLMResultAnalyzer(llm).analyze("员工数量是多少？", candidate)

    assert analysis.answer == "当前查询结果为 4。"
    assert analysis.key_findings[0].evidence == "SQL result: cnt = 4"
