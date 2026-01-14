"""Direct test of SemanticChunker to debug chunking issue."""

import sys

sys.path.insert(0, "src")

from ingestion.semantic_chunker import SemanticChunker
from pathlib import Path

# Read demo file
demo_file = Path("demo_data/postgres_investments.sql")
with open(demo_file, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Testing SemanticChunker on {demo_file.name}")
print(f"File: {len(content)} chars, {len(content.splitlines())} lines")
print("=" * 60)

# Test with postgres dialect
chunker = SemanticChunker(dialect="postgres")
chunks = chunker.chunk_file(content, str(demo_file))

print(f"\n✅ Chunking complete!")
print(f"   Total chunks: {len(chunks)}")
print(f"   Chunker dialect: {chunker.dialect}")

# Show chunk details
for i, chunk in enumerate(chunks[:10]):
    print(f"\nChunk {i+1}:")
    print(f"   Type: {chunk.chunk_type.value}")
    print(f"   Length: {len(chunk.content)} chars")
    print(f"   Tokens: {chunk.token_count}")
    print(f"   Tables: {chunk.tables_referenced}")
    print(f"   Preview: {chunk.content[:80]}...")

if len(chunks) > 10:
    print(f"\n... and {len(chunks) - 10} more chunks")
