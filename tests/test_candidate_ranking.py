from sql_agent.ranking.ranker import CandidateRanker


def test_candidate_ranker_selects_executable_aggregate_sql(sql_database, sample_table_descriptions):
    ranker = CandidateRanker(sql_database, sample_table_descriptions)

    ranked = ranker.rank(
        question="员工数量是多少？",
        candidates=[
            "SELECT * FROM employees",
            "SELECT COUNT(*) AS cnt FROM employees",
            "SELECT COUNT(*) FROM payroll",
        ],
    )

    assert ranked[0].sql == "SELECT COUNT(*) AS cnt FROM employees"
    assert ranked[0].status == "VALID"
    assert ranked[0].execution.row_count == 1
    assert "执行成功" in ranked[0].evidence

    invalid = [candidate for candidate in ranked if "payroll" in candidate.sql][0]
    assert invalid.status == "INVALID"
    assert invalid.score < ranked[0].score
    assert "不在允许的 schema 白名单" in invalid.evidence
    assert invalid.safety["allowed"] is False
    assert invalid.safety["violations"]


def test_candidate_ranker_deduplicates_sql(sql_database, sample_table_descriptions):
    ranker = CandidateRanker(sql_database, sample_table_descriptions)

    ranked = ranker.rank(
        question="列出员工",
        candidates=[
            "SELECT * FROM employees",
            "SELECT * FROM employees;",
            "  SELECT * FROM employees  ",
        ],
    )

    assert len(ranked) == 1
    assert ranked[0].sql == "SELECT * FROM employees"
    assert ranked[0].safety["allowed"] is True
