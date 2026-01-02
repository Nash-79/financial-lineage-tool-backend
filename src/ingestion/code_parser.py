"""
This module provides the CodeParser class, which is responsible for parsing
source code files (e.g., SQL, Python) to extract lineage information.
It uses the sqlglot library to parse SQL and trace column-level lineage.
"""

from sqlglot import exp
from sqlglot import parse_one
import ast
import json


class CodeParser:
    """
    Parses code to extract metadata, dependencies, and lineage.
    """

    def parse_sql(self, sql_content: str, dialect: str = "tsql"):
        """
        Parses a SQL string to extract detailed lineage information, including
        tables, views, functions, and column-level transformations.

        Args:
            sql_content: The SQL script as a string.
            dialect: The SQL dialect to use (e.g., 'tsql', 'spark', 'bigquery').

        Returns:
            A dictionary containing structured information about the SQL script,
            or None if parsing fails.
        """
        try:
            ast = parse_one(sql_content, read=dialect)
            if not ast:
                return None

            result = {
                "read": set(),
                "write": None,
                "columns": [],
                "functions_and_procedures": set(),
                "views": set(),
            }

            # Find write table/view
            if isinstance(ast, (exp.CreateTable, exp.Insert, exp.Update, exp.Create)):
                kind = ast.args.get("kind", "").upper()
                if kind == "VIEW":
                    result["views"].add(ast.this.sql())
                    result["write"] = ast.this.sql()
                elif kind in ("FUNCTION", "PROCEDURE"):
                    result["functions_and_procedures"].add(ast.this.sql())
                elif isinstance(ast.this, exp.Table):
                    result["write"] = ast.this.sql()

            # Find all tables being read from
            for table in ast.find_all(exp.Table):
                # Ensure we don't add the write table to the read list
                if table.sql() != result["write"]:
                    result["read"].add(table.sql())

            # Extract column level lineage if it's a SELECT statement
            if hasattr(ast, "expression") and isinstance(ast.expression, exp.Select):
                select_expression = ast.expression
                for projection in select_expression.find_all(exp.Alias):
                    target_col = projection.this
                    lineage = projection.expression.lineage()

                    source_cols = {col.sql() for col in lineage.find_all(exp.Column)}

                    result["columns"].append(
                        {
                            "target": target_col.sql(),
                            "sources": list(source_cols),
                            "transformation": projection.expression.sql(
                                dialect=dialect
                            ),
                        }
                    )
                # Handle columns without aliases
                for col in select_expression.selects:
                    if not isinstance(col, exp.Alias):
                        lineage = col.lineage()
                        source_cols = {c.sql() for c in lineage.find_all(exp.Column)}
                        result["columns"].append(
                            {
                                "target": col.this.sql(),
                                "sources": list(source_cols),
                                "transformation": col.sql(dialect=dialect),
                            }
                        )

            # Convert sets to lists for JSON serialization
            result["read"] = list(result["read"])
            result["functions_and_procedures"] = list(
                result["functions_and_procedures"]
            )
            result["views"] = list(result["views"])

            # If no specific write table, it might just be a select query
            if not result["write"] and (result["read"] or result["columns"]):
                result["write"] = "console"

            return result

        except Exception as e:
            # Optionally log the error
            print(f"Error parsing SQL with sqlglot: {e}")
            return None

    def parse_python(self, python_content: str):
        """
        Parses Python code to extract classes, functions, and imports.

        Args:
            python_content: Python source code.

        Returns:
            Dict with 'classes', 'functions', 'imports'.
        """
        try:
            tree = ast.parse(python_content)
            result = {
                "classes": [],
                "functions": [],
                "imports": [],
                "docstring": ast.get_docstring(tree),
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    result["classes"].append(
                        {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "bases": [
                                b.id for b in node.bases if isinstance(b, ast.Name)
                            ],
                        }
                    )
                elif isinstance(node, ast.FunctionDef):
                    # We might want to track which class a method belongs to
                    # usage of 'ast.walk' flatly visits all nodes.
                    # For simple lineage, flat list of functions is okay for now.
                    result["functions"].append(
                        {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "args": [arg.arg for arg in node.args.args],
                        }
                    )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        result["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        result["imports"].append(f"{module}.{alias.name}")

            return result
        except Exception as e:
            print(f"Error parsing Python: {e}")
            return None

    def parse_json(self, json_content: str):
        """
        Parses JSON content to extract structure.

        Args:
            json_content: JSON string.

        Returns:
            Dict representing the JSON structure or metadata.
        """
        try:
            data = json.loads(json_content)
            result = {"type": type(data).__name__, "keys": [], "array_length": 0}

            if isinstance(data, dict):
                result["keys"] = list(data.keys())
            elif isinstance(data, list):
                result["array_length"] = len(data)
                if len(data) > 0 and isinstance(data[0], dict):
                    # Heuristic: if list of dicts, capture keys of first item
                    result["keys"] = list(data[0].keys())

            return result
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return None


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
