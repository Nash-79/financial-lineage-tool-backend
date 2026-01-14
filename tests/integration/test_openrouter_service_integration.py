"""Integration-style test for OpenRouterService HTTP behavior."""

from __future__ import annotations

import json

import httpx
import pytest

from src.services.inference_service import OpenRouterService


class MockTransport:
    """Mock transport that fails on response_format then succeeds."""

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        if "response_format" in payload:
            return httpx.Response(400, json={"error": "unsupported response_format"})
        content = json.dumps(
            {
                "edges": [
                    {
                        "source_node": "urn:li:Table:proj:alpha",
                        "target_node": "urn:li:Table:proj:beta",
                        "relationship_type": "READS",
                        "confidence": 0.9,
                        "reasoning": "mocked",
                    }
                ]
            }
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )


@pytest.mark.asyncio
async def test_openrouter_service_fallback_request():
    service = OpenRouterService(api_key="test-key")
    service.client = httpx.AsyncClient(transport=httpx.MockTransport(MockTransport()))
    try:
        proposals = await service.predict_lineage("select * from t", [])
        assert len(proposals) == 1
        assert proposals[0].relationship_type == "READS"
    finally:
        await service.close()
