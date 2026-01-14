import sys
import os

sys.path.append(os.getcwd())

from src.ingestion.semantic_chunker import SemanticChunker
from pathlib import Path


def debug_tsql():
    file_path = "demo_data/sql_Investments_objects.sql"
    content = Path(file_path).read_text(encoding="utf-8")

    print(f"--- Debugging {file_path} ---")

    # 1. Try default chunking (which seems to be failing to keep procs together)
    chunker = SemanticChunker(dialect="tsql")
    chunks = chunker.chunk_file(content, file_path)

    print(f"\nGenerated {len(chunks)} chunks.")

    # Print chunk headers to see splits
    for i, c in enumerate(chunks):
        first_line = c.content.strip().split("\n")[0]
        print(f"[{i:03d}] {c.chunk_type.name}: {first_line[:60]}...")
        if "usp_LoadFactDailyPnL" in c.content:
            print(f"      -> Contains usp_LoadFactDailyPnL")


if __name__ == "__main__":
    debug_tsql()
