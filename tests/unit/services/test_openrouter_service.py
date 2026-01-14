"""Unit tests for OpenRouterService."""

import pytest
from unittest.mock import AsyncMock

from src.services.inference_service import OpenRouterService


@pytest.mark.asyncio
async def test_predict_lineage_parses_edges():
    service = OpenRouterService(api_key="test-key")
    service._call_openrouter = AsyncMock(
        return_value={
            "edges": [
                {
                    "source_node": "node_a",
                    "target_node": "node_b",
                    "relationship_type": "READS",
                    "confidence": 0.82,
                    "reasoning": "uses table in query",
                }
            ]
        }
    )

    try:
        proposals = await service.predict_lineage("SELECT * FROM t", ["node_a"])
        assert len(proposals) == 1
        assert proposals[0].source_node == "node_a"
        assert proposals[0].target_node == "node_b"
        assert proposals[0].confidence == 0.82
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_predict_lineage_skips_invalid_edges():
    service = OpenRouterService(api_key="test-key")
    service._call_openrouter = AsyncMock(
        return_value={
            "edges": [
                {"source_node": "node_a"},
                {
                    "source_node": "node_a",
                    "target_node": "node_b",
                    "relationship_type": "READS",
                    "confidence": 0.6,
                    "reasoning": "ok",
                },
            ]
        }
    )

    try:
        proposals = await service.predict_lineage("SELECT * FROM t", ["node_a"])
        assert len(proposals) == 1
        assert proposals[0].target_node == "node_b"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_enforce_free_tier_downgrades():
    service = OpenRouterService(api_key="test-key")
    model = service._enforce_free_tier("openai/gpt-4o")
    assert model == "google/gemini-2.0-flash-exp:free"
    await service.close()
