"""Remote LLM clients for Groq and OpenRouter API providers.

Provides unified interface for calling cloud-based LLM providers with free tiers.
All providers use 100% free models to avoid API costs.
"""

from __future__ import annotations

import json
import logging
import httpx
from typing import AsyncIterator

from src.llm.circuit_breaker import RateLimitError

logger = logging.getLogger(__name__)


class GroqClient:
    """Client for Groq API (free tier available)."""

    def __init__(self, api_key: str, timeout: float = 120.0):
        """Initialize Groq client."""
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://api.groq.com/openai/v1"

    async def generate(
        self,
        prompt: str,
        model: str = "llama-3.1-70b-versatile",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate text completion using Groq API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if response.status_code == 429:
                logger.warning("Groq rate limit hit (model: %s)", model)
                raise RateLimitError("Groq rate limit exceeded")
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        model: str = "llama-3.1-70b-versatile",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text completion using Groq API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as response:
                if response.status_code == 429:
                    raise RateLimitError("Groq rate limit exceeded")
                response.raise_for_status()

                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: ") and chunk != "data: [DONE]":
                        data = json.loads(chunk[6:])
                        if data.get("choices") and data["choices"][0].get(
                            "delta", {}
                        ).get("content"):
                            yield data["choices"][0]["delta"]["content"]


class OpenRouterClient:
    """Client for OpenRouter API (free tier available).

    Free models available:
    - google/gemini-2.0-flash-exp:free
    - mistralai/mistral-7b-instruct:free
    - mistralai/devstral-2512:free
    - meta-llama/llama-3.1-8b-instruct:free
    - deepseek/deepseek-r1:free
    """

    def __init__(self, api_key: str, timeout: float = 120.0):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key from openrouter.ai
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://openrouter.ai/api/v1"

    async def generate(
        self,
        prompt: str,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate text completion using OpenRouter API.

        Args:
            prompt: Input prompt
            model: Model name (must use :free suffix)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text

        Raises:
            RateLimitError: If rate limit is hit
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/your-repo",  # Required by OpenRouter
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )

                if response.status_code == 429:
                    logger.warning(f"OpenRouter rate limit hit (model: {model})")
                    raise RateLimitError("OpenRouter rate limit exceeded")

                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

            except httpx.HTTPError as e:
                logger.error(f"OpenRouter API error: {e}")
                raise

    async def generate_stream(
        self,
        prompt: str,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text completion using OpenRouter API.

        Args:
            prompt: Input prompt
            model: Model name (must use :free suffix)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Token strings as they are generated
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-repo",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as response:
                if response.status_code == 429:
                    raise RateLimitError("OpenRouter rate limit exceeded")

                response.raise_for_status()

                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: ") and chunk != "data: [DONE]":
                        import json

                        data = json.loads(chunk[6:])
                        if data.get("choices") and data["choices"][0].get(
                            "delta", {}
                        ).get("content"):
                            yield data["choices"][0]["delta"]["content"]
