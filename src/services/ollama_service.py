"""Ollama LLM service client."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Optional, Any

import httpx


from ..api.config import config

# Cache TTL in seconds (24 hours)
EMBEDDING_CACHE_TTL = 86400
logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for local Ollama LLM service.

    Provides methods for text generation and embeddings using Ollama's
    local API. Supports any Ollama-compatible model with optional Redis caching.

    Attributes:
        host: Ollama server URL (e.g., "http://localhost:11434").
        client: Async HTTP client for API requests.
        redis: Optional Redis client for embedding cache.
        cache_hits: Counter for cache hit statistics.
        cache_misses: Counter for cache miss statistics.
    """

    def __init__(self, host: str, redis_client: Optional[Any] = None):
        """Initialize Ollama client.

        Args:
            host: Ollama server URL.
            redis_client: Optional Redis client for caching embeddings.
        """
        self.host = host
        self.client = httpx.AsyncClient(timeout=120.0)
        self.redis = redis_client
        self.cache_hits = 0
        self.cache_misses = 0

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str = "",
        temperature: float = 0.1,
    ) -> str:
        """Generate text using Ollama.

        Args:
            prompt: User prompt text.
            model: Model name to use (e.g., "llama3.1:8b").
            system: System prompt for context.
            temperature: Sampling temperature (0.0-1.0).

        Returns:
            Generated text response.

        Raises:
            Exception: If Ollama request fails.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.post(
            f"{self.host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_ctx": config.OLLAMA_CONTEXT_WINDOW,
                },
            },
        )

        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")

        return response.json()["message"]["content"]

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key from text content hash.

        Args:
            text: Text to embed.
            model: Model name (included in key for model-specific embeddings).

        Returns:
            Cache key string.
        """
        content_hash = hashlib.md5(f"{model}:{text}".encode()).hexdigest()
        return f"embed:{content_hash}"

    async def embed(self, text: str, model: str) -> list[float]:
        """Generate embeddings using Ollama with optional Redis caching.

        Checks Redis cache first (if available) to avoid redundant Ollama calls.
        Cache hits significantly reduce latency for repeated queries.

        Args:
            text: Text to embed.
            model: Embedding model name (e.g., "nomic-embed-text").

        Returns:
            Embedding vector (768-dimensional for nomic-embed-text).

        Raises:
            Exception: If embedding request fails.
        """
        # Check cache first
        if self.redis:
            try:
                cache_key = self._get_cache_key(text, model)
                cached = await self.redis.get(cache_key)
                if cached:
                    self.cache_hits += 1
                    return json.loads(cached)
            except Exception as e:
                # Cache failure shouldn't block embedding
                logger.warning("Embedding cache read failed: %s", e)

        # Cache miss - call Ollama
        self.cache_misses += 1
        response = await self.client.post(
            f"{self.host}/api/embeddings", json={"model": model, "prompt": text}
        )

        if response.status_code != 200:
            raise Exception(f"Ollama embedding error: {response.text}")

        embedding = response.json()["embedding"]

        # Store in cache
        if self.redis:
            try:
                cache_key = self._get_cache_key(text, model)
                await self.redis.setex(
                    cache_key, EMBEDDING_CACHE_TTL, json.dumps(embedding)
                )
            except Exception as e:
                # Cache failure shouldn't block response
                logger.warning("Embedding cache write failed: %s", e)

        return embedding

    def get_cache_stats(self) -> dict:
        """Get embedding cache statistics.

        Returns:
            Dictionary with cache_hits, cache_misses, and hit_rate.
        """
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0.0
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(hit_rate, 3),
        }

    async def embed_batch(
        self,
        texts: list[str],
        model: str,
        batch_size: int = 50,
    ) -> list[list[float]]:
        """Batch embedding with caching and size splitting.

        Args:
            texts: List of texts to embed.
            model: Embedding model name.
            batch_size: Max number of texts per batch (default 50).

        Returns:
            List of embeddings in the same order as provided texts.
        """
        if not texts:
            return []

        async def fetch_one(text: str) -> list[float]:
            return await self.embed(text, model=model)

        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await asyncio.gather(*(fetch_one(t) for t in batch))
            results.extend(embeddings)
        return results

    async def warm_cache(
        self, texts: list[str], model: str, batch_size: int = 50
    ) -> None:
        """Pre-populate embedding cache for a set of texts."""
        if not texts:
            return
        try:
            await self.embed_batch(texts, model=model, batch_size=batch_size)
        except Exception as exc:
            logger.warning("Cache warming failed: %s", exc)

    async def generate_stream(
        self,
        prompt: str,
        model: str,
        system: str = "",
        temperature: float = 0.1,
    ):
        """Generate text using Ollama with streaming response.

        Yields response chunks as they are generated by the LLM.

        Args:
            prompt: User prompt text.
            model: Model name to use (e.g., "llama3.1:8b").
            system: System prompt for context.
            temperature: Sampling temperature (0.0-1.0).

        Yields:
            String chunks of the generated response.

        Raises:
            Exception: If Ollama request fails.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with self.client.stream(
            "POST",
            f"{self.host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_ctx": config.OLLAMA_CONTEXT_WINDOW,
                },
            },
        ) as response:
            if response.status_code != 200:
                raise Exception(f"Ollama streaming error: {response.status_code}")

            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        await self.client.aclose()
