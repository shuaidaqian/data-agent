from sql_agent.sql.scanner import SchemaScanner


def test_schema_scanner_writes_sample_values_to_column_metadata(sql_database):
    scanner = SchemaScanner(sql_database)

    employees = [
        table
        for table in scanner.scan_all_tables("db1")
        if table and table.table_name == "employees"
    ][0]

    name_column = next(column for column in employees.columns if column.name == "name")
    assert name_column.sample_values
    assert "Alice" in name_column.sample_values
    assert name_column.low_cardinality
    assert "Alice" in name_column.categories
