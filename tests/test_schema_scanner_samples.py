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


def test_schema_scanner_adds_column_semantics_and_synonyms(sql_database):
    scanner = SchemaScanner(sql_database)

    employees = [
        table
        for table in scanner.scan_all_tables("db1")
        if table and table.table_name == "employees"
    ][0]

    salary_column = next(column for column in employees.columns if column.name == "salary")
    department_id_column = next(
        column for column in employees.columns if column.name == "department_id"
    )
    hire_date_column = next(column for column in employees.columns if column.name == "hire_date")
    name_column = next(column for column in employees.columns if column.name == "name")

    assert salary_column.semantic_type == "measure"
    assert "数值" in salary_column.synonyms
    assert department_id_column.semantic_type == "foreign_key"
    assert hire_date_column.semantic_type == "date"
    assert "日期" in hire_date_column.synonyms
    assert name_column.semantic_type == "name"
    assert "名称" in name_column.synonyms
