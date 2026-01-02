"""Ollama LLM service client."""

from __future__ import annotations

import httpx


class OllamaClient:
    """Client for local Ollama LLM service.

    Provides methods for text generation and embeddings using Ollama's
    local API. Supports any Ollama-compatible model.

    Attributes:
        host: Ollama server URL (e.g., "http://localhost:11434").
        client: Async HTTP client for API requests.
    """

    def __init__(self, host: str):
        """Initialize Ollama client.

        Args:
            host: Ollama server URL.
        """
        self.host = host
        self.client = httpx.AsyncClient(timeout=120.0)

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
                "options": {"temperature": temperature},
            },
        )

        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")

        return response.json()["message"]["content"]

    async def embed(self, text: str, model: str) -> list[float]:
        """Generate embeddings using Ollama.

        Args:
            text: Text to embed.
            model: Embedding model name (e.g., "nomic-embed-text").

        Returns:
            Embedding vector.

        Raises:
            Exception: If embedding request fails.
        """
        response = await self.client.post(
            f"{self.host}/api/embeddings", json={"model": model, "prompt": text}
        )

        if response.status_code != 200:
            raise Exception(f"Ollama embedding error: {response.text}")

        return response.json()["embedding"]

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        await self.client.aclose()
