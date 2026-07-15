import pytest
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, text as sa_text
from sqlalchemy.orm import declarative_base
from datetime import date
from sql_agent.sql.database import SQLDatabase
from sql_agent.core.types import DatabaseConnection, TableDescription, ColumnMetadata

Base = declarative_base()

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    location = Column(String(100))

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    salary = Column(Float)
    department_id = Column(Integer, ForeignKey("departments.id"))
    hire_date = Column(Date)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Float)
    category = Column(String(50))

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    employee_id = Column(Integer, ForeignKey("employees.id"))
    quantity = Column(Integer)
    sale_date = Column(Date)
    amount = Column(Float)

DATA = [
    ("INSERT INTO departments VALUES (1, 'Engineering', 'Building A')", None),
    ("INSERT INTO departments VALUES (2, 'Sales', 'Building B')", None),
    ("INSERT INTO departments VALUES (3, 'HR', 'Building A')", None),
    ("INSERT INTO employees VALUES (1, 'Alice', 80000, 1, '2020-01-15')", None),
    ("INSERT INTO employees VALUES (2, 'Bob', 65000, 1, '2021-03-20')", None),
    ("INSERT INTO employees VALUES (3, 'Charlie', 75000, 2, '2019-06-10')", None),
    ("INSERT INTO employees VALUES (4, 'Diana', 70000, 3, '2022-08-05')", None),
    ("INSERT INTO products VALUES (1, 'Widget A', 10.99, 'Widgets')", None),
    ("INSERT INTO products VALUES (2, 'Widget B', 15.99, 'Widgets')", None),
    ("INSERT INTO products VALUES (3, 'Gadget X', 25.99, 'Gadgets')", None),
    ("INSERT INTO products VALUES (4, 'Gadget Y', 35.99, 'Gadgets')", None),
    ("INSERT INTO sales VALUES (1, 1, 1, 10, '2023-01-10', 109.90)", None),
    ("INSERT INTO sales VALUES (2, 2, 1, 5, '2023-01-15', 79.95)", None),
    ("INSERT INTO sales VALUES (3, 3, 3, 3, '2023-02-01', 77.97)", None),
    ("INSERT INTO sales VALUES (4, 1, 2, 8, '2023-02-15', 87.92)", None),
    ("INSERT INTO sales VALUES (5, 4, 3, 2, '2023-03-01', 71.98)", None),
]

@pytest.fixture(scope="session")
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for sql, _ in DATA:
            conn.execute(sa_text(sql))
        conn.commit()
    yield engine

@pytest.fixture
def sql_database(sqlite_engine):
    return SQLDatabase(sqlite_engine, dialect="sqlite")

@pytest.fixture
def db_connection():
    return DatabaseConnection(id="test_db_1", alias="test_db", connection_uri="sqlite:///:memory:")

@pytest.fixture
def sample_table_descriptions():
    return [
        TableDescription(table_name="employees", columns=[
            ColumnMetadata(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnMetadata(name="name", data_type="VARCHAR", description="Employee full name"),
            ColumnMetadata(name="salary", data_type="FLOAT", description="Annual salary"),
            ColumnMetadata(name="department_id", data_type="INTEGER", is_foreign_key=True, foreign_key_ref="departments.id"),
            ColumnMetadata(name="hire_date", data_type="DATE"),
        ], table_schema="CREATE TABLE employees (id INTEGER PRIMARY KEY, name VARCHAR, salary FLOAT, department_id INTEGER, hire_date DATE)", description="Employee records"),
        TableDescription(table_name="departments", columns=[
            ColumnMetadata(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnMetadata(name="name", data_type="VARCHAR", description="Department name"),
            ColumnMetadata(name="location", data_type="VARCHAR"),
        ], table_schema="CREATE TABLE departments (id INTEGER PRIMARY KEY, name VARCHAR, location VARCHAR)", description="Department info"),
        TableDescription(table_name="sales", columns=[
            ColumnMetadata(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnMetadata(name="product_id", data_type="INTEGER", is_foreign_key=True, foreign_key_ref="products.id"),
            ColumnMetadata(name="employee_id", data_type="INTEGER", is_foreign_key=True, foreign_key_ref="employees.id"),
            ColumnMetadata(name="quantity", data_type="INTEGER"),
            ColumnMetadata(name="amount", data_type="FLOAT", description="Total sale amount"),
        ], table_schema="CREATE TABLE sales (id INTEGER PRIMARY KEY, product_id INTEGER, employee_id INTEGER, quantity INTEGER, amount FLOAT)"),
        TableDescription(table_name="products", columns=[
            ColumnMetadata(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnMetadata(name="name", data_type="VARCHAR"),
            ColumnMetadata(name="price", data_type="FLOAT"),
            ColumnMetadata(name="category", data_type="VARCHAR"),
        ], table_schema="CREATE TABLE products (id INTEGER PRIMARY KEY, name VARCHAR, price FLOAT, category VARCHAR)"),
    ]
