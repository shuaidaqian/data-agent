from sql_agent.sql.complex_sql import ComplexSQLDecomposer


class TestComplexSQL:
    def test_is_complex_join(self):
        assert ComplexSQLDecomposer.is_complex_query("average salary per department and compare")

    def test_is_not_complex(self):
        assert not ComplexSQLDecomposer.is_complex_query("Show all employees")

    def test_is_complex_ranking(self):
        assert ComplexSQLDecomposer.is_complex_query("Show top 10 products by sales")

    def test_query_type_time_series(self):
        assert ComplexSQLDecomposer.get_query_type("Month over month sales") == "time_series"

    def test_query_type_comparison(self):
        assert ComplexSQLDecomposer.get_query_type("Compare sales Q1 and Q2") == "comparison"

    def test_query_type_ranking(self):
        assert ComplexSQLDecomposer.get_query_type("Top 3 employees") == "ranking"

    def test_query_type_general(self):
        assert ComplexSQLDecomposer.get_query_type("Show departments") == "general"
