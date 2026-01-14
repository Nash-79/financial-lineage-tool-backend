"""Test sqlglot parsing on postgres_investments.sql to debug chunking."""

import sqlglot
from pathlib import Path

# Read the demo file
demo_file = Path("demo_data/postgres_investments.sql")
with open(demo_file, "r", encoding="utf-8") as f:
    content = f.read()

print(f"File size: {len(content)} chars, {len(content.splitlines())} lines")
print("\n" + "=" * 60)
print("Testing sqlglot.parse() with postgres dialect")
print("=" * 60)

# Try parsing with postgres dialect
try:
    statements = sqlglot.parse(content, dialect="postgres")
    print(f"\n✅ Parsed successfully!")
    print(f"   Total statements: {len(statements)}")
    print(f"   Non-None statements: {len([s for s in statements if s is not None])}")

    # Show first few statements
    for i, stmt in enumerate(statements[:5]):
        if stmt:
            stmt_sql = stmt.sql(dialect="postgres")
            print(f"\nStatement {i+1} ({type(stmt).__name__}):")
            print(f"   Length: {len(stmt_sql)} chars")
            print(f"   Preview: {stmt_sql[:100]}...")
        else:
            print(f"\nStatement {i+1}: None")

    if len(statements) > 5:
        print(f"\n... and {len(statements) - 5} more statements")

except Exception as e:
    print(f"\n❌ Parsing failed: {e}")
    print(f"   Error type: {type(e).__name__}")

# Also test statement splitting by semicolons
print("\n" + "=" * 60)
print("Manual semicolon count")
print("=" * 60)
semicolons = content.count(";")
print(f"Total semicolons: {semicolons}")
print("(Should give rough idea of expected statement count)")
