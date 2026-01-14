"""Integration tests for hybrid search with sparse + dense vectors."""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from src.services.qdrant_service import QdrantLocalClient


def _qdrant_host_port() -> tuple[str, int]:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return host, port


@pytest.mark.asyncio
async def test_hybrid_search_returns_relevant_hit():
    host, port = _qdrant_host_port()
    client = QdrantLocalClient(host, port)
    collection = f"test_hybrid_{uuid.uuid4().hex[:8]}"

    try:
        try:
            resp = await client.client.get(f"{client.base_url}/collections")
            resp.raise_for_status()
        except httpx.HTTPError:
            pytest.skip("Qdrant not available for hybrid search integration test")

        await client.create_collection(collection, vector_size=3, enable_hybrid=True)

        await client.upsert(
            collection,
            points=[
                {
                    "id": 1,
                    "vector": [1.0, 0.0, 0.0],
                    "sparse_vector": client.build_sparse_vector("alpha asset"),
                    "payload": {"tag": "alpha", "file_path": "alpha.sql"},
                },
                {
                    "id": 2,
                    "vector": [0.0, 1.0, 0.0],
                    "sparse_vector": client.build_sparse_vector("beta asset"),
                    "payload": {"tag": "beta", "file_path": "beta.sql"},
                },
            ],
        )

        results = await client.hybrid_search(
            collection,
            query_text="alpha",
            dense_vector=[1.0, 0.0, 0.0],
            limit=1,
        )

        assert results, "Expected at least one hybrid search result"
        assert results[0]["payload"]["tag"] == "alpha"
    finally:
        try:
            await client.client.delete(f"{client.base_url}/collections/{collection}")
        except httpx.HTTPError:
            pass
        await client.client.aclose()
