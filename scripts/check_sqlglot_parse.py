"""Check sqlglot parsing result type."""

import sqlglot
from sqlglot import exp
from pathlib import Path

demo_file = Path("demo_data/postgres_investments.sql")
with open(demo_file, "r", encoding="utf-8") as f:
    content = f.read()

try:
    statements = sqlglot.parse(content, dialect="postgres")
    print(f"Parsed {len(statements)} statements.")

    if statements:
        stmt = statements[0]
        print(f"Statement 0 type: {type(stmt)}")
        print(f"Statement 0 exp type: {type(stmt).__name__}")
        if isinstance(stmt, exp.Command):
            print("It is a Command expression.")

        # Check if it covers the whole file
        print(f"Statement SQL length: {len(stmt.sql())}")
        print(f"Original content length: {len(content)}")

except Exception as e:
    print(f"Parse failed: {e}")
