import json

import pytest

from src.services.ollama_service import OllamaClient


class DummyRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value


@pytest.mark.asyncio
async def test_embed_batch_uses_cache(monkeypatch):
    redis = DummyRedis()
    client = OllamaClient(host="http://localhost:11434", redis_client=redis)

    calls = 0

    async def fake_embed(self, text, model):
        cache_key = client._get_cache_key(text, model)
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
        nonlocal calls
        calls += 1
        return [len(text)]

    monkeypatch.setattr(OllamaClient, "embed", fake_embed, raising=False)

    texts = ["a", "b", "c"]
    res1 = await client.embed_batch(texts, model="m")
    assert res1 == [[1], [1], [1]]
    assert calls == 3

    # Populate cache manually to simulate hits
    for text in texts:
        key = client._get_cache_key(text, "m")
        await redis.setex(key, 100, "[42]")

    res2 = await client.embed_batch(texts, model="m")
    assert res2 == [[42], [42], [42]]
    # Calls should not increase because embed reads from cache
    assert calls == 3
