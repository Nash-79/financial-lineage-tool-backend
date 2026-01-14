"""Debug postgres chunking issue."""

import sys

sys.path.insert(0, "src")

from ingestion.semantic_chunker import SemanticChunker
from pathlib import Path

# Test postgres file
demo_file = Path("demo_data/postgres_investments.sql")
with open(demo_file, "r", encoding="utf-8") as f:
    content = f.read()

print(f"File: {demo_file.name}")
print(f"Size: {len(content)} chars, {content.count(';')} semicolons")
print("=" * 60)

# Test chunking
chunker = SemanticChunker(dialect="postgres")
print(f"Chunker dialect: {chunker.dialect}")
print(f"Max tokens: {chunker.chunkers['sql'].max_tokens}")

# Force fallback by using a dialect that might trigger it?
# Actually we can just call _fallback_chunk directly to test it
print("\nCalling _fallback_chunk directly...")
chunks = chunker.chunkers["sql"]._fallback_chunk(content, str(demo_file))

print(f"\n✅ Created {len(chunks)} chunks")
for i, c in enumerate(chunks):
    print(f"Chunk {i}: {len(c.content)} chars, {c.token_count} tokens")
    print(f"Preview: {c.content[:50]}...")

# Count tokens in full file
total_tokens = chunker.chunkers["sql"].count_tokens(content)
print(f"Total file tokens: {total_tokens}")
print(f"Max tokens per chunk: {chunker.chunkers['sql'].max_tokens}")

if len(chunks) == 1:
    print(f"\n⚠️ WARNING: Only 1 chunk created!")
    print(f"Chunk tokens: {chunks[0].token_count}")
    print(f"Chunk type: {chunks[0].chunk_type.value}")

    # Test semicolon split manually
    statements = content.split(";")
    print(f"\nManual split: {len(statements)} statements")
    for i, stmt in enumerate(statements[:5]):
        stmt = stmt.strip()
        if stmt:
            tokens = chunker.chunkers["sql"].count_tokens(stmt)
            print(f"  Statement {i+1}: {tokens} tokens, {len(stmt)} chars")
