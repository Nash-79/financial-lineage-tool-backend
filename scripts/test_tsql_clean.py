import sys
import os
import re
from pathlib import Path
import sqlglot


def test_clean_parsing():
    content = Path("demo_data/sql_Investments_objects.sql").read_text(encoding="utf-8")

    # Clean GO statements
    # Remove "GO" on its own line (with optional whitespace)
    cleaned = re.sub(r"(?m)^\s*GO\s*$", "", content)

    print("--- Testing Cleaned Content Parsing ---")
    statements = sqlglot.parse(cleaned, read="tsql")

    print(f"Parsed {len(statements)} statements.")

    for i, stmt in enumerate(statements):
        sql = stmt.sql(dialect="tsql")
        lines = sql.splitlines()
        first_line = lines[0] if lines else ""
        print(f"[{i:03d}] {first_line[:80]}")

        # Check if usp_LoadFactDailyPnL is fully contained in one chunk
        if "usp_LoadFactDailyPnL" in sql:
            print(f"      -> Contains usp_LoadFactDailyPnL")
            if "INSERT INTO core.FactDailyPnL" in sql and "END" in sql:
                print("      [SUCCESS] Contains body and END!")
            else:
                print("      [FAIL] Fragmented body.")


if __name__ == "__main__":
    test_clean_parsing()
