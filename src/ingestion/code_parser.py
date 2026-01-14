"""
This module provides the CodeParser class, which is responsible for parsing
source code files (e.g., SQL, Python) to extract lineage information.
It uses the sqlglot library to parse SQL and trace column-level lineage.
"""

from .plugins.json_enricher import JsonEnricherPlugin
from .plugins.python_ast import PythonAstPlugin
from .plugins.sql_standard import StandardSqlPlugin


class CodeParser:
    """
    Parses code to extract metadata, dependencies, and lineage.
    """

    def __init__(self) -> None:
        self.sql_plugin = StandardSqlPlugin()
        self.python_plugin = PythonAstPlugin()
        self.json_plugin = JsonEnricherPlugin()

    def parse_sql(self, sql_content: str, dialect: str = "auto"):
        """
        Parses a SQL string to extract detailed lineage information, including
        tables, views, functions, and column-level transformations.

        Args:
            sql_content: The SQL script as a string.
            dialect: The SQL dialect to use (e.g., 'tsql', 'spark', 'bigquery'), or 'auto' for default.

        Returns:
            A dictionary containing structured information about the SQL script,
            or None if parsing fails.
        """
        result = self.sql_plugin.parse(sql_content, {"dialect": dialect})
        return result.metadata.get("parsed")

    def parse_python(self, python_content: str):
        """
        Parses Python code to extract classes, functions, and imports.

        Args:
            python_content: Python source code.

        Returns:
            Dict with 'classes', 'functions', 'imports'.
        """
        result = self.python_plugin.parse(python_content, {})
        return result.metadata.get("parsed")

    def parse_json(self, json_content: str):
        """
        Parses JSON content to extract structure.

        Args:
            json_content: JSON string.

        Returns:
            Dict representing the JSON structure or metadata.
        """
        result = self.json_plugin.parse(json_content, {})
        return result.metadata.get("parsed")


if __name__ == "__main__":
    # Example Usage
    parser = CodeParser()
    import json

    def print_json(data):
        print(json.dumps(data, indent=2))

    print("--- Example 1: CREATE TABLE AS SELECT (Column Lineage) ---")
    sql1 = """
    CREATE TABLE target_db.dbo.fact_sales AS
    SELECT
        s.sale_id as sale_identifier,
        p.product_name,
        c.customer_name,
        CAST(s.sale_date AS DATE) as event_date,
        s.quantity * p.price as total_amount
    FROM staging.sales s
    JOIN staging.products p ON s.product_id = p.product_id
    JOIN staging.customers c ON s.customer_id = c.customer_id
    WHERE s.status = 'COMPLETED';
    """
    lineage1 = parser.parse_sql(sql1, dialect="duckdb")
    print_json(lineage1)

    print("\n--- Example 2: CREATE VIEW ---")
    sql2 = """
    CREATE VIEW reporting.vw_customer_summary AS
    SELECT
        customer_id,
        COUNT(order_id) as number_of_orders,
        SUM(total_amount) as total_spent
    FROM fact_orders
    GROUP BY 1;
    """
    lineage2 = parser.parse_sql(sql2, dialect="tsql")
    print_json(lineage2)

    print("\n--- Example 3: CREATE FUNCTION ---")
    sql3 = """
    CREATE FUNCTION dbo.get_full_name(@first_name VARCHAR(50), @last_name VARCHAR(50))
    RETURNS VARCHAR(101) AS
    BEGIN
        RETURN @first_name + ' ' + @last_name;
    END;
    """
    lineage3 = parser.parse_sql(sql3, dialect="tsql")
    print_json(lineage3)

    print("\n--- Example 4: CREATE PROCEDURE ---")
    sql4 = """
    CREATE OR ALTER PROCEDURE dbo.usp_update_stock
        @product_id INT,
        @quantity_sold INT
    AS
    BEGIN
        SET NOCOUNT ON;
        UPDATE products.stock
        SET quantity = quantity - @quantity_sold
        WHERE product_id = @product_id;
    END;
    """
    lineage4 = parser.parse_sql(sql4, dialect="tsql")
    print_json(lineage4)

    print("\n--- Example 5: Simple SELECT with transformation ---")
    sql5 = """
    SELECT
        CONCAT(first_name, ' ', last_name) as full_name,
        customer_id
    FROM raw.customers
    """
    lineage5 = parser.parse_sql(sql5, dialect="tsql")
    print_json(lineage5)
