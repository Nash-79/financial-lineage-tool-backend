"""
Export embeddings to JSON format.
(Wrapper for src.utils.exporters)
"""

import sys
import os
import asyncio
from pathlib import Path

# Ensure src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.exporters import EmbeddingExporter


async def main():
    print(
        """
    ================================================================
              Embeddings Export to JSON
    ================================================================
    """
    )

    exporter = EmbeddingExporter()

    try:
        # Example 1: Export sample text embeddings
        print("\n[1] Generating sample text embeddings...")
        sample_texts = [
            "Customer table containing customer information",
            "Transaction table with sales data",
            "Product catalog with pricing",
            "Order history and fulfillment data",
        ]
        await exporter.export_text_embeddings(
            sample_texts, "data/sample_embeddings.json"
        )

        # Example 2: Export SQL embeddings
        print("\n[2] Generating SQL statement embeddings...")
        sql_file = "data/sample_financial_schema.sql"
        if Path(sql_file).exists():
            await exporter.export_sql_embeddings(sql_file, "data/sql_embeddings.json")
        else:
            print(f"[!] SQL file not found: {sql_file}")

        # Example 3: Export Neo4j entity embeddings
        print("\n[3] Generating Neo4j entity embeddings...")
        await exporter.export_entity_embeddings("data/entity_embeddings.json")

        print("\n" + "=" * 64)
        print("[+] All embedding exports completed successfully!")
        print("=" * 64)

    except Exception as e:
        print(f"\n[!] Error: {e}")
    finally:
        await exporter.close()


if __name__ == "__main__":
    asyncio.run(main())
