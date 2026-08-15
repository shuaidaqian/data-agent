from sql_agent.security.policy import SQLSafetyPolicy
from sql_agent.security.sql_safety import SQLSafetyValidator
from sql_agent.security.types import SQLViolationType


def test_sql_ast_safety_allows_join_alias_columns(sample_table_descriptions):
    validator = SQLSafetyValidator(sample_table_descriptions, dialect="sqlite")

    report = validator.validate(
        "SELECT e.name, d.name " "FROM employees e JOIN departments d ON e.department_id = d.id"
    )

    assert report.allowed is True
    assert report.tables == ["departments", "employees"]
    assert "employees.name" in report.columns
    assert "departments.name" in report.columns
    assert report.violations == []


def test_sql_ast_safety_allows_cte_and_subquery(sample_table_descriptions):
    validator = SQLSafetyValidator(sample_table_descriptions, dialect="sqlite")

    report = validator.validate(
        """
        WITH active_departments AS (
            SELECT id FROM departments WHERE location = 'Building A'
        )
        SELECT name FROM employees
        WHERE department_id IN (SELECT id FROM active_departments)
        """
    )

    assert report.allowed is True
    assert report.tables == ["departments", "employees"]
    assert "departments.location" in report.columns
    assert "employees.department_id" in report.columns


def test_sql_ast_safety_rejects_non_select_and_multi_statement(sample_table_descriptions):
    validator = SQLSafetyValidator(sample_table_descriptions, dialect="sqlite")

    delete_report = validator.validate("DELETE FROM employees")
    multi_report = validator.validate("SELECT name FROM employees; DROP TABLE employees;")

    assert delete_report.allowed is False
    assert delete_report.violations[0].type == SQLViolationType.NON_SELECT_STATEMENT.value
    assert multi_report.allowed is False
    assert multi_report.violations[0].type == SQLViolationType.MULTI_STATEMENT.value


def test_sql_ast_safety_rejects_unknown_table_and_column(sample_table_descriptions):
    validator = SQLSafetyValidator(sample_table_descriptions, dialect="sqlite")

    table_report = validator.validate("SELECT id FROM payroll")
    column_report = validator.validate("SELECT secret_salary FROM employees")

    assert table_report.allowed is False
    assert table_report.violations[0].type == SQLViolationType.UNKNOWN_TABLE.value
    assert column_report.allowed is False
    assert column_report.violations[0].type == SQLViolationType.UNKNOWN_COLUMN.value


def test_sql_ast_safety_rejects_ambiguous_unqualified_column(sample_table_descriptions):
    validator = SQLSafetyValidator(sample_table_descriptions, dialect="sqlite")

    report = validator.validate(
        "SELECT id FROM employees JOIN departments ON employees.department_id = departments.id"
    )

    assert report.allowed is False
    assert report.violations[0].type == SQLViolationType.AMBIGUOUS_COLUMN.value
    assert report.violations[0].column == "id"


def test_sql_ast_safety_select_star_is_policy_controlled(sample_table_descriptions):
    strict = SQLSafetyValidator(sample_table_descriptions, dialect="sqlite")
    permissive = SQLSafetyValidator(
        sample_table_descriptions,
        policy=SQLSafetyPolicy(allow_select_star=True),
        dialect="sqlite",
    )

    strict_report = strict.validate("SELECT * FROM employees")
    permissive_report = permissive.validate("SELECT * FROM employees")

    assert strict_report.allowed is False
    assert strict_report.violations[0].type == SQLViolationType.STAR_NOT_ALLOWED.value
    assert permissive_report.allowed is True
