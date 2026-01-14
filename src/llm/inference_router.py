"""Inference router with hybrid local-first strategy and automatic fallback.

Routes LLM requests to local Ollama by default, with automatic fallback to
cloud providers (Groq, OpenRouter) when Ollama is unavailable or OOM.
"""

from __future__ import annotations

import asyncio
import logging
import tiktoken
from typing import Awaitable, Optional, Callable

from src.api.config import config
from src.llm.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimitError,
)
from src.llm.free_tier import DEFAULT_FREE_TIER_MODEL, enforce_free_tier
from src.llm.remote_clients import GroqClient, OpenRouterClient
from src.services.ollama_service import OllamaClient

logger = logging.getLogger(__name__)


class OOMError(Exception):
    """Raised when Ollama runs out of memory."""

    pass


class CancelledRequestError(Exception):
    """Raised when an inference request is cancelled."""

    pass


class InferenceRouter:
    """Routes LLM inference requests with hybrid local-first strategy.

    Modes:
    - local-first (default): Try Ollama, fallback to cloud on OOM
    - cloud-only: Skip Ollama, use cloud providers directly
    - local-only: Ollama only, no fallback (privacy mode)

    Example:
        >>> router = InferenceRouter(mode="local-first")
        >>> response = await router.generate("Explain SQL lineage")
    """

    def __init__(
        self,
        mode: str = "local-first",
        ollama_service: OllamaClient | None = None,
    ):
        """Initialize inference router.

        Args:
            mode: Inference mode (local-first, cloud-only, local-only)
            ollama_service: Optional OllamaClient instance (creates one if not provided)
        """
        self.mode = mode
        self.ollama = ollama_service or OllamaClient(host=config.OLLAMA_HOST)

        # Initialize remote clients if API keys are available
        self.groq: GroqClient | None = None
        self.openrouter: OpenRouterClient | None = None

        if config.GROQ_API_KEY:
            self.groq = GroqClient(api_key=config.GROQ_API_KEY)
            logger.info("Groq client initialized")

        if config.OPENROUTER_API_KEY:
            self.openrouter = OpenRouterClient(api_key=config.OPENROUTER_API_KEY)
            logger.info("OpenRouter client initialized")

        # Circuit breakers for rate limiting
        self.groq_breaker = CircuitBreaker(cooldown_seconds=60, name="groq")
        self.openrouter_breaker = CircuitBreaker(cooldown_seconds=60, name="openrouter")

        # Metrics
        self.requests_total = 0
        self.ollama_requests = 0
        self.groq_requests = 0
        self.openrouter_requests = 0
        self.fallback_count = 0
        self.oom_errors = 0
        self.free_tier_downgrades = 0

        logger.info(f"InferenceRouter initialized (mode: {self.mode})")

    async def generate(
        self,
        prompt: str,
        user_selected_model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> str:
        """Generate text completion with automatic fallback.

        Args:
            prompt: Input prompt
            user_selected_model: Optional specific model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text

        Raises:
            Exception: If all providers fail
        """
        self.requests_total += 1
        tokens = self._estimate_tokens(prompt)

        # Honor user-selected model if provided
        if user_selected_model:
            return await self._generate_with_model(
                prompt, user_selected_model, max_tokens, temperature, cancellation_event
            )

        # Mode-based routing
        if self.mode == "cloud-only":
            return await self._generate_cloud(
                prompt, max_tokens, temperature, cancellation_event
            )
        elif self.mode == "local-only":
            return await self._generate_ollama(
                prompt, max_tokens, temperature, cancellation_event
            )
        else:  # local-first (default)
            return await self._generate_local_first(
                prompt, tokens, max_tokens, temperature, cancellation_event
            )

    async def _generate_local_first(
        self,
        prompt: str,
        tokens: int,
        max_tokens: int,
        temperature: float,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> str:
        """Local-first strategy with automatic fallback.

        Args:
            prompt: Input prompt
            tokens: Estimated token count
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        # Check Ollama health and token count
        health_ok = await self._check_ollama_health()

        if health_ok and tokens < 3000:
            try:
                self.ollama_requests += 1
                return await self._generate_ollama(
                    prompt, max_tokens, temperature, cancellation_event
                )
            except OOMError:
                logger.warning("Ollama OOM, falling back to cloud provider")
                self.oom_errors += 1
                self.fallback_count += 1
                return await self._generate_cloud(
                    prompt, max_tokens, temperature, cancellation_event
                )
        else:
            # Large query or Ollama unhealthy, use cloud directly
            if tokens >= 3000:
                logger.info(f"Large query ({tokens} tokens), routing to cloud")
            else:
                logger.warning("Ollama unhealthy, routing to cloud")

            self.fallback_count += 1
            return await self._generate_cloud(
                prompt, max_tokens, temperature, cancellation_event
            )

    async def _generate_ollama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> str:
        """Generate using local Ollama with automatic quantized model selection.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text

        Raises:
            OOMError: If Ollama runs out of memory
        """
        try:
            # Use quantized model if OLLAMA_USE_QUANTIZED=true (50% memory reduction)
            model = config.get_llm_model()

            # Call Ollama generate method
            response = await self._await_with_cancellation(
                self.ollama.generate(
                    prompt=prompt, model=model, temperature=temperature
                ),
                cancellation_event,
                cleanup=self._cleanup_ollama,
            )
            return response
        except CancelledRequestError:
            logger.info("Ollama request cancelled")
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "out of memory" in error_msg or "oom" in error_msg:
                raise OOMError("Ollama out of memory") from e
            raise

    async def _generate_cloud(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> str:
        """Generate using cloud provider (Groq or OpenRouter).

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text

        Raises:
            Exception: If all cloud providers fail
        """
        # Provider selection based on configuration
        # - Groq: Faster (30 req/min free), but less reliable under load
        # - OpenRouter: Slower, but more reliable for degradation scenarios
        # Set INFERENCE_FALLBACK_PROVIDER=openrouter for degradation mode

        # Try Groq first (faster, preferred) unless OpenRouter is explicitly configured
        if self.groq and config.INFERENCE_FALLBACK_PROVIDER != "openrouter":
            try:
                self.groq_requests += 1
                result = await self._await_with_cancellation(
                    self.groq_breaker.call(
                        self.groq.generate,
                        prompt,
                        model=config.INFERENCE_DEFAULT_MODEL,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    cancellation_event,
                )
                logger.info("Generated response using Groq")
                return result
            except (RateLimitError, CircuitBreakerOpenError) as e:
                logger.warning(f"Groq unavailable: {e}, trying OpenRouter")
            except Exception as e:
                logger.error(f"Groq error: {e}, trying OpenRouter")

        # Fallback to OpenRouter
        if self.openrouter:
            try:
                self.openrouter_requests += 1
                model = self._enforce_free_tier(config.INFERENCE_DEFAULT_MODEL)
                result = await self._await_with_cancellation(
                    self.openrouter_breaker.call(
                        self.openrouter.generate,
                        prompt,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    cancellation_event,
                )
                logger.info("Generated response using OpenRouter")
                return result
            except Exception as e:
                logger.error(f"OpenRouter error: {e}")
                raise

        raise Exception("No cloud providers available or all failed")

    async def _generate_with_model(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> str:
        """Generate using specific model.

        Args:
            prompt: Input prompt
            model: Specific model identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        # Determine provider from model name
        if ":" in model or model.startswith("llama3"):
            # Ollama model
            self.ollama_requests += 1
            response = await self._await_with_cancellation(
                self.ollama.generate(
                    prompt=prompt, model=model, temperature=temperature
                ),
                cancellation_event,
                cleanup=self._cleanup_ollama,
            )
            return response
        elif "/" in model:
            # OpenRouter model
            if not self.openrouter:
                raise ValueError("OpenRouter not configured")
            self.openrouter_requests += 1
            model = self._enforce_free_tier(model)
            return await self._await_with_cancellation(
                self.openrouter.generate(
                    prompt, model=model, max_tokens=max_tokens, temperature=temperature
                ),
                cancellation_event,
            )
        else:
            # Groq model
            if not self.groq:
                raise ValueError("Groq not configured")
            self.groq_requests += 1
            return await self._await_with_cancellation(
                self.groq.generate(
                    prompt, model=model, max_tokens=max_tokens, temperature=temperature
                ),
                cancellation_event,
            )

    async def _check_ollama_health(self) -> bool:
        """Check if Ollama is healthy and ready.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple health check - try to list models
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{config.OLLAMA_HOST}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback to rough estimate (1 token ~= 4 characters)
            return len(text) // 4

    def get_metrics(self) -> dict:
        """Get inference routing metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "requests_total": self.requests_total,
            "ollama_requests": self.ollama_requests,
            "groq_requests": self.groq_requests,
            "openrouter_requests": self.openrouter_requests,
            "fallback_count": self.fallback_count,
            "free_tier_downgrades": self.free_tier_downgrades,
            "fallback_rate": (
                self.fallback_count / self.requests_total
                if self.requests_total > 0
                else 0
            ),
            "oom_errors": self.oom_errors,
            "groq_circuit_breaker": self.groq_breaker.get_metrics(),
            "openrouter_circuit_breaker": self.openrouter_breaker.get_metrics(),
        }

    def _enforce_free_tier(self, model: str) -> str:
        """Ensure OpenRouter models remain on the free tier."""
        selected_model, downgraded = enforce_free_tier(model)
        if downgraded:
            self.free_tier_downgrades += 1
            logger.warning(
                "Downgrading model '%s' to free tier model '%s'",
                model,
                DEFAULT_FREE_TIER_MODEL,
            )
        return selected_model

    async def _await_with_cancellation(
        self,
        coro: Awaitable,
        cancellation_event: Optional[asyncio.Event],
        cleanup: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """Await a coroutine while honoring cancellation events.

        If the cancellation_event is set while the coroutine is running,
        cancel it and raise CancelledRequestError. Optional cleanup is awaited
        when cancellation occurs to close underlying transports.
        """
        if cancellation_event is None:
            return await coro

        task = asyncio.create_task(coro)
        wait_task = asyncio.create_task(cancellation_event.wait())

        done, pending = await asyncio.wait(
            {task, wait_task}, return_when=asyncio.FIRST_COMPLETED
        )

        if wait_task in done and cancellation_event.is_set():
            task.cancel()
            if cleanup:
                try:
                    await cleanup()
                except Exception as cleanup_err:
                    logger.debug(f"Cleanup after cancellation failed: {cleanup_err}")
            raise CancelledRequestError("Inference request cancelled")

        # Cancellation not triggered; ensure waiter is cleaned up
        wait_task.cancel()
        return await task

    async def _cleanup_ollama(self):
        """Close Ollama client connections after cancellation."""
        try:
            await self.ollama.client.aclose()
        except Exception as e:
            logger.debug(f"Failed to cleanup Ollama client: {e}")
