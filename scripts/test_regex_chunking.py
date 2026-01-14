"""Test regex patterns on postgres_investments.sql."""

import re
from pathlib import Path

# Read postgres file
demo_file = Path("demo_data/postgres_investments.sql")
with open(demo_file, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Testing regex on {demo_file.name}")
print(f"Size: {len(content)} chars")

patterns = {
    "TABLE": r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP\s+|TEMPORARY\s+)?TABLE",
    "VIEW": r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW",
    "FUNCTION": r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION",
    "PROCEDURE": r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:PROCEDURE|PROC)",
    "TRIGGER": r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER",
    "INDEX": r"CREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+)?(?:NONCLUSTERED\s+)?INDEX",
    "SCHEMA": r"CREATE\s+SCHEMA",
}

objects = []
for domain_type, pattern in patterns.items():
    for match in re.finditer(pattern, content, re.IGNORECASE):
        objects.append(
            {"type": domain_type, "start": match.start(), "match": match.group(0)}
        )

objects.sort(key=lambda x: x["start"])

print(f"\nFound {len(objects)} objects:")
for obj in objects:
    print(f"- {obj['type']}: {obj['match']} (at {obj['start']})")

if not objects:
    print("\nNo objects found!")
