import pytest
from sql_agent.sql.schema_linking import SchemaLinker

class TestSchemaLinker:
    @pytest.fixture
    def linker(self, sample_table_descriptions):
        return SchemaLinker(sample_table_descriptions)

    def test_find_join_paths(self, linker):
        paths = linker.find_join_paths(["employees", "departments"])
        assert len(paths) >= 1
        assert "employees" in paths[0]["from_table"]

    def test_find_entity_table(self, linker):
        matches = linker.find_entity_in_schema("employee")
        tables = [m for m in matches if m["type"] == "table"]
        assert len(tables) >= 1

    def test_find_entity_column(self, linker):
        matches = linker.find_entity_in_schema("salary")
        cols = [m for m in matches if m["type"] == "column"]
        assert len(cols) >= 1

    def test_join_graph_summary(self, linker):
        s = linker.get_join_graph_summary()
        assert "ForeignKey" in s or "employees" in s

    def test_bfs_find_path(self, linker):
        path = linker.find_join_path_between_tables("employees", "departments")
        assert path is not None
        assert "departments" in path

    def test_bfs_no_path(self, linker):
        path = linker.find_join_path_between_tables("employees", "nonexistent")
        assert path is None

    def test_empty_table_list(self, linker):
        assert len(linker.find_join_paths([])) == 0

    def test_single_table_no_join(self, linker):
        assert len(linker.find_join_paths(["employees"])) == 0
