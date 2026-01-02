"""
SQL Classifier - Identifies SQL object types from SQL code.

This module analyzes SQL statements to determine what type of database
object is being created (table, view, function, stored procedure, etc.).
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from sqlglot import exp, parse


class SQLObjectType(str, Enum):
    """Types of SQL database objects."""

    TABLE = "table"
    VIEW = "view"
    FUNCTION = "function"
    PROCEDURE = "procedure"
    TRIGGER = "trigger"
    INDEX = "index"
    SCHEMA = "schema"
    UNKNOWN = "unknown"


@dataclass
class SQLObject:
    """Represents a classified SQL object."""

    object_type: SQLObjectType
    name: str
    schema: Optional[str] = None
    database: Optional[str] = None
    sql_content: str = ""
    start_line: int = 0
    end_line: int = 0

    def get_full_name(self) -> str:
        """Get fully qualified object name."""
        parts = []
        if self.database:
            parts.append(self.database)
        if self.schema:
            parts.append(self.schema)
        parts.append(self.name)
        return ".".join(parts)

    def get_filename(self) -> str:
        """Generate a safe filename for this object."""
        # Use simple name, make it filesystem-safe
        safe_name = re.sub(r"[^\w\-_.]", "_", self.name)
        return f"{safe_name}.sql"


class SQLClassifier:
    """
    Classifies SQL statements into object types.

    Supports:
    - CREATE TABLE
    - CREATE VIEW
    - CREATE FUNCTION / CREATE FUNCTION
    - CREATE PROCEDURE / CREATE PROC
    - CREATE TRIGGER
    - CREATE INDEX
    - CREATE SCHEMA
    """

    def __init__(self, dialect: str = "tsql"):
        """
        Initialize the classifier.

        Args:
            dialect: SQL dialect (tsql, postgres, mysql, etc.)
        """
        self.dialect = dialect

    def classify_file(self, file_content: str) -> List[SQLObject]:
        """
        Classify all SQL objects in a file.

        Args:
            file_content: The SQL file content

        Returns:
            List of classified SQL objects
        """
        objects = []

        # Try using sqlglot first
        try:
            objects = self._classify_with_sqlglot(file_content)
        except Exception as e:
            print(f"Sqlglot parsing failed: {e}, falling back to regex")
            objects = self._classify_with_regex(file_content)

        return objects

    def _classify_with_sqlglot(self, content: str) -> List[SQLObject]:
        """Classify using sqlglot AST parsing."""
        objects = []

        # Parse all statements
        statements = parse(content, dialect=self.dialect)

        for stmt in statements:
            if stmt is None:
                continue

            obj = self._classify_statement(stmt)
            if obj:
                objects.append(obj)

        return objects

    def _classify_statement(self, stmt: exp.Expression) -> Optional[SQLObject]:
        """Classify a single sqlglot statement."""

        # CREATE TABLE
        if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":
            return self._extract_table(stmt)

        # CREATE VIEW
        if isinstance(stmt, exp.Create) and stmt.kind == "VIEW":
            return self._extract_view(stmt)

        # CREATE FUNCTION
        if isinstance(stmt, exp.Create) and stmt.kind == "FUNCTION":
            return self._extract_function(stmt)

        # CREATE PROCEDURE
        if isinstance(stmt, exp.Create) and stmt.kind == "PROCEDURE":
            return self._extract_procedure(stmt)

        # CREATE INDEX
        if isinstance(stmt, exp.Create) and stmt.kind == "INDEX":
            return self._extract_index(stmt)

        # CREATE SCHEMA
        if isinstance(stmt, exp.Create) and stmt.kind == "SCHEMA":
            return self._extract_schema(stmt)

        return None

    def _extract_table(self, stmt: exp.Create) -> SQLObject:
        """Extract table information."""
        table_name = stmt.this

        name = table_name.name if hasattr(table_name, "name") else str(table_name)
        schema = table_name.db if hasattr(table_name, "db") else None
        database = table_name.catalog if hasattr(table_name, "catalog") else None

        return SQLObject(
            object_type=SQLObjectType.TABLE,
            name=name,
            schema=schema,
            database=database,
            sql_content=stmt.sql(dialect=self.dialect),
        )

    def _extract_view(self, stmt: exp.Create) -> SQLObject:
        """Extract view information."""
        view_name = stmt.this

        name = view_name.name if hasattr(view_name, "name") else str(view_name)
        schema = view_name.db if hasattr(view_name, "db") else None
        database = view_name.catalog if hasattr(view_name, "catalog") else None

        return SQLObject(
            object_type=SQLObjectType.VIEW,
            name=name,
            schema=schema,
            database=database,
            sql_content=stmt.sql(dialect=self.dialect),
        )

    def _extract_function(self, stmt: exp.Create) -> SQLObject:
        """Extract function information."""
        func_name = stmt.this

        name = func_name.name if hasattr(func_name, "name") else str(func_name)
        schema = func_name.db if hasattr(func_name, "db") else None

        return SQLObject(
            object_type=SQLObjectType.FUNCTION,
            name=name,
            schema=schema,
            sql_content=stmt.sql(dialect=self.dialect),
        )

    def _extract_procedure(self, stmt: exp.Create) -> SQLObject:
        """Extract procedure information."""
        proc_name = stmt.this

        name = proc_name.name if hasattr(proc_name, "name") else str(proc_name)
        schema = proc_name.db if hasattr(proc_name, "db") else None

        return SQLObject(
            object_type=SQLObjectType.PROCEDURE,
            name=name,
            schema=schema,
            sql_content=stmt.sql(dialect=self.dialect),
        )

    def _extract_index(self, stmt: exp.Create) -> SQLObject:
        """Extract index information."""
        return SQLObject(
            object_type=SQLObjectType.INDEX,
            name=str(stmt.this),
            sql_content=stmt.sql(dialect=self.dialect),
        )

    def _extract_schema(self, stmt: exp.Create) -> SQLObject:
        """Extract schema information."""
        return SQLObject(
            object_type=SQLObjectType.SCHEMA,
            name=str(stmt.this),
            sql_content=stmt.sql(dialect=self.dialect),
        )

    def _classify_with_regex(self, content: str) -> List[SQLObject]:
        """Fallback classification using regex patterns."""
        objects = []

        # Remove comments for better matching
        cleaned = self._remove_comments(content)

        # Patterns for different object types
        patterns = {
            SQLObjectType.TABLE: r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)",
            SQLObjectType.VIEW: r"CREATE\s+(?:OR\s+(?:ALTER|REPLACE)\s+)?VIEW\s+([^\s(]+)",
            SQLObjectType.FUNCTION: r"CREATE\s+(?:OR\s+(?:ALTER|REPLACE)\s+)?FUNCTION\s+([^\s(]+)",
            SQLObjectType.PROCEDURE: r"CREATE\s+(?:OR\s+(?:ALTER|REPLACE)\s+)?(?:PROCEDURE|PROC)\s+([^\s(]+)",
            SQLObjectType.TRIGGER: r"CREATE\s+(?:OR\s+(?:ALTER|REPLACE)\s+)?TRIGGER\s+([^\s(]+)",
            SQLObjectType.INDEX: r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+([^\s(]+)",
            SQLObjectType.SCHEMA: r"CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s;]+)",
        }

        for obj_type, pattern in patterns.items():
            matches = re.finditer(pattern, cleaned, re.IGNORECASE)
            for match in matches:
                full_name = match.group(1).strip()

                # Extract schema and name
                parts = full_name.split(".")
                if len(parts) == 3:
                    database, schema, name = parts
                elif len(parts) == 2:
                    database = None
                    schema, name = parts
                else:
                    database = None
                    schema = None
                    name = parts[0]

                # Find the full statement
                sql_content = self._extract_statement(content, match.start())

                objects.append(
                    SQLObject(
                        object_type=obj_type,
                        name=name,
                        schema=schema,
                        database=database,
                        sql_content=sql_content,
                    )
                )

        return objects

    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments."""
        # Remove single-line comments
        sql = re.sub(r"--[^\n]*", "", sql)
        # Remove multi-line comments
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        return sql

    def _extract_statement(self, content: str, start_pos: int) -> str:
        """
        Extract the full statement starting from a position.

        Looks for the statement ending (semicolon or GO keyword).
        """
        # Find the next semicolon or GO statement
        remaining = content[start_pos:]

        # Look for semicolon
        semicolon_pos = remaining.find(";")

        # Look for GO (T-SQL batch separator)
        go_match = re.search(r"\bGO\b", remaining, re.IGNORECASE)
        go_pos = go_match.start() if go_match else -1

        # Use whichever comes first
        if semicolon_pos >= 0 and go_pos >= 0:
            end_pos = min(semicolon_pos, go_pos)
        elif semicolon_pos >= 0:
            end_pos = semicolon_pos
        elif go_pos >= 0:
            end_pos = go_pos
        else:
            # No clear ending, take rest of file
            end_pos = len(remaining)

        statement = remaining[: end_pos + 1].strip()
        return statement

    def classify_single_statement(self, sql_statement: str) -> SQLObject:
        """
        Classify a single SQL statement.

        Args:
            sql_statement: A single SQL CREATE statement

        Returns:
            Classified SQL object
        """
        objects = self.classify_file(sql_statement)

        if objects:
            return objects[0]

        # Return unknown if classification fails
        return SQLObject(
            object_type=SQLObjectType.UNKNOWN, name="unknown", sql_content=sql_statement
        )


# Convenience function
def classify_sql(sql_content: str, dialect: str = "tsql") -> List[SQLObject]:
    """
    Classify SQL objects in content.

    Args:
        sql_content: SQL code to classify
        dialect: SQL dialect

    Returns:
        List of classified SQL objects
    """
    classifier = SQLClassifier(dialect=dialect)
    return classifier.classify_file(sql_content)


if __name__ == "__main__":
    # Test the classifier
    test_sql = """
    -- Create customer table
    CREATE TABLE dbo.customers (
        customer_id INT PRIMARY KEY,
        name VARCHAR(100)
    );

    -- Create view
    CREATE VIEW dbo.vw_active_customers AS
    SELECT * FROM dbo.customers WHERE active = 1;

    -- Create function
    CREATE FUNCTION dbo.get_customer_name(@customer_id INT)
    RETURNS VARCHAR(100)
    AS
    BEGIN
        RETURN (SELECT name FROM dbo.customers WHERE customer_id = @customer_id);
    END;

    -- Create stored procedure
    CREATE PROCEDURE dbo.usp_update_customer
        @customer_id INT,
        @name VARCHAR(100)
    AS
    BEGIN
        UPDATE dbo.customers
        SET name = @name
        WHERE customer_id = @customer_id;
    END;
    """

    classifier = SQLClassifier()
    objects = classifier.classify_file(test_sql)

    print("Found objects:")
    for obj in objects:
        print(f"  - {obj.object_type.value.upper()}: {obj.get_full_name()}")
