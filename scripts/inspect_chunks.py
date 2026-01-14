"""Inspect chunks in Qdrant to verify ingestion quality."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.qdrant_service import QdrantLocalClient
from src.api.config import config


async def inspect():
    qdrant = QdrantLocalClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

    # Get collection info
    info = await qdrant.collection_info(config.QDRANT_COLLECTION)
    print(f"Collection Info: {info}")
    total = info.get("result", {}).get("points_count", "unknown")
    print(f"Total chunks: {total}")

    # Scroll through chunks using raw HTTP request
    print("\n--- Postgres Chunks ---")

    # Manually call scroll API to get ALL chunks for this file
    print("\n--- Object Split Verification ---")

    scroll_url = (
        f"{qdrant.base_url}/collections/{config.QDRANT_COLLECTION}/points/scroll"
    )
    all_chunks = []
    next_offset = None

    while True:
        payload = {
            "filter": {
                "must": [
                    {"key": "file_path", "match": {"text": "postgres_investments.sql"}}
                ]
            },
            "limit": 100,
            "with_payload": True,
        }
        if next_offset:
            payload["offset"] = next_offset

        response = await qdrant.client.post(scroll_url, json=payload)
        result = response.json().get("result", {})
        batch = result.get("points", [])

        if not batch:
            break

        all_chunks.extend(batch)
        next_offset = result.get("next_page_offset")
        if not next_offset:
            break

    print(f"Total chunks found for 'postgres_investments.sql': {len(all_chunks)}")

    # Analyze chunk types
    type_counts = {}
    for point in all_chunks:
        payload = point.get("payload", {})
        ctype = payload.get("chunk_type", "unknown")
        type_counts[ctype] = type_counts.get(ctype, 0) + 1

    print("\n[Object Distribution]")
    for ctype, count in type_counts.items():
        print(f"  - {ctype}: {count}")

    # List specific objects found
    print("\n[Found Objects]")
    for point in all_chunks:
        payload = point.get("payload", {})
        content = payload.get("content", "")
        ctype = payload.get("chunk_type", "")

        # Extract object name from content for display
        name = "unknown"
        first_line = content.strip().split("\n")[0]
        if "CREATE OR REPLACE FUNCTION" in first_line:
            name = first_line.split("FUNCTION")[1].split("(")[0].strip()
        elif "CREATE TABLE" in first_line:
            name = first_line.split("TABLE")[1].split("(")[0].strip()
        elif "CREATE TRIGGER" in first_line:
            name = first_line.split("TRIGGER")[1].split()[0].strip()
        elif "SCHEMA" in first_line:
            name = first_line

        print(f"  [{ctype}] {name[:50]}")

    await qdrant.close()


if __name__ == "__main__":
    asyncio.run(inspect())
