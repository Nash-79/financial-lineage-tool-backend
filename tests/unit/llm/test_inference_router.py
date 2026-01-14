"""Unit tests for InferenceRouter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.llm.inference_router import InferenceRouter, OOMError
from src.llm.circuit_breaker import RateLimitError


class TestInferenceRouter:
    """Test suite for InferenceRouter."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch("src.llm.inference_router.config") as mock_cfg:
            mock_cfg.GROQ_API_KEY = "test-groq-key"
            mock_cfg.OPENROUTER_API_KEY = "test-openrouter-key"
            mock_cfg.INFERENCE_FALLBACK_PROVIDER = "groq"
            mock_cfg.INFERENCE_DEFAULT_MODEL = "llama-3.1-70b-versatile"
            mock_cfg.OLLAMA_HOST = "http://localhost:11434"
            mock_cfg.get_llm_model.return_value = "llama3.1:8b"
            yield mock_cfg

    @pytest.fixture
    def mock_ollama_service(self):
        """Mock OllamaService."""
        service = MagicMock()
        service.generate = AsyncMock()
        return service

    @pytest.fixture
    def router(self, mock_config, mock_ollama_service):
        """Create InferenceRouter instance for testing."""
        return InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

    @pytest.mark.asyncio
    async def test_initialization_local_first(self, mock_config, mock_ollama_service):
        """Test InferenceRouter initialization in local-first mode."""
        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

        assert router.mode == "local-first"
        assert router.ollama is not None
        assert router.groq is not None  # Should initialize with API key
        assert router.openrouter is not None
        assert router.requests_total == 0
        assert router.ollama_requests == 0
        assert router.groq_requests == 0
        assert router.openrouter_requests == 0
        assert router.fallback_count == 0
        assert router.oom_errors == 0

    @pytest.mark.asyncio
    async def test_initialization_cloud_only(self, mock_config, mock_ollama_service):
        """Test InferenceRouter initialization in cloud-only mode."""
        router = InferenceRouter(
            mode="cloud-only",
            ollama_service=mock_ollama_service,
        )

        assert router.mode == "cloud-only"

    @pytest.mark.asyncio
    async def test_initialization_local_only(self, mock_config, mock_ollama_service):
        """Test InferenceRouter initialization in local-only mode."""
        router = InferenceRouter(
            mode="local-only",
            ollama_service=mock_ollama_service,
        )

        assert router.mode == "local-only"

    @pytest.mark.asyncio
    async def test_initialization_without_api_keys(self, mock_ollama_service):
        """Test initialization when API keys are not set."""
        with patch("src.llm.inference_router.config") as mock_cfg:
            mock_cfg.GROQ_API_KEY = ""
            mock_cfg.OPENROUTER_API_KEY = ""
            mock_cfg.OLLAMA_HOST = "http://localhost:11434"
            mock_cfg.get_llm_model.return_value = "llama3.1:8b"

            router = InferenceRouter(
                mode="local-only",
                ollama_service=mock_ollama_service,
            )

            assert router.groq is None
            assert router.openrouter is None

    @pytest.mark.asyncio
    async def test_generate_local_first_success(self, router):
        """Test successful generation in local-first mode."""
        # Mock Ollama health check
        with patch.object(router, "_check_ollama_health", return_value=True):
            # Mock Ollama generation
            router.ollama.generate.return_value = {
                "response": "Test response from Ollama"
            }

            result = await router.generate(
                prompt="Test prompt",
                max_tokens=100,
                temperature=0.7,
            )

            assert result == "Test response from Ollama"
            assert router.requests_total == 1
            assert router.ollama_requests == 1
            assert router.groq_requests == 0
            assert router.fallback_count == 0

    @pytest.mark.asyncio
    async def test_generate_local_first_oom_fallback(self, router):
        """Test OOM fallback in local-first mode."""
        # Mock Ollama health check
        with patch.object(router, "_check_ollama_health", return_value=True):
            # Mock Ollama to raise OOM error
            router.ollama.generate.side_effect = Exception("out of memory")

            # Mock Groq fallback
            with patch.object(
                router.groq, "generate", new=AsyncMock(return_value="Groq response")
            ):
                result = await router.generate(
                    prompt="Test prompt",
                    max_tokens=100,
                    temperature=0.7,
                )

                assert result == "Groq response"
                assert router.requests_total == 1
                assert router.ollama_requests == 1
                assert router.groq_requests == 1
                assert router.fallback_count == 1
                assert router.oom_errors == 1

    @pytest.mark.asyncio
    async def test_generate_local_first_large_query_routes_to_cloud(self, router):
        """Test that large queries (>3000 tokens) route to cloud directly."""
        # Create large prompt (>12000 characters = >3000 tokens)
        large_prompt = "A" * 15000

        with patch.object(router, "_check_ollama_health", return_value=True):
            # Mock Groq
            with patch.object(
                router.groq, "generate", new=AsyncMock(return_value="Groq response")
            ):
                result = await router.generate(
                    prompt=large_prompt,
                    max_tokens=100,
                    temperature=0.7,
                )

                assert result == "Groq response"
                assert router.ollama_requests == 0  # Should skip Ollama
                assert router.groq_requests == 1
                assert router.fallback_count == 1

    @pytest.mark.asyncio
    async def test_generate_local_first_ollama_unhealthy(self, router):
        """Test fallback when Ollama is unhealthy."""
        # Mock Ollama health check to fail
        with patch.object(router, "_check_ollama_health", return_value=False):
            # Mock Groq
            with patch.object(
                router.groq, "generate", new=AsyncMock(return_value="Groq response")
            ):
                result = await router.generate(
                    prompt="Test prompt",
                    max_tokens=100,
                    temperature=0.7,
                )

                assert result == "Groq response"
                assert router.ollama_requests == 0
                assert router.groq_requests == 1
                assert router.fallback_count == 1

    @pytest.mark.asyncio
    async def test_generate_cloud_only_mode(self, router):
        """Test generation in cloud-only mode."""
        router.mode = "cloud-only"

        with patch.object(
            router.groq, "generate", new=AsyncMock(return_value="Groq response")
        ):
            result = await router.generate(
                prompt="Test prompt",
                max_tokens=100,
                temperature=0.7,
            )

            assert result == "Groq response"
            assert router.ollama_requests == 0
            assert router.groq_requests == 1

    @pytest.mark.asyncio
    async def test_generate_local_only_mode(self, router):
        """Test generation in local-only mode."""
        router.mode = "local-only"

        router.ollama.generate.return_value = {"response": "Ollama response"}

        result = await router.generate(
            prompt="Test prompt",
            max_tokens=100,
            temperature=0.7,
        )

        assert result == "Ollama response"
        assert router.ollama_requests == 1
        assert router.groq_requests == 0

    @pytest.mark.asyncio
    async def test_generate_with_user_selected_model_ollama(self, router):
        """Test generation with user-selected Ollama model."""
        router.ollama.generate.return_value = {"response": "Custom model response"}

        result = await router.generate(
            prompt="Test",
            user_selected_model="llama3.1:8b-q4_0",
        )

        assert result == "Custom model response"
        router.ollama.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_user_selected_model_groq(self, router):
        """Test generation with user-selected Groq model."""
        with patch.object(
            router.groq, "generate", new=AsyncMock(return_value="Groq custom")
        ):
            result = await router.generate(
                prompt="Test",
                user_selected_model="llama-3.1-70b-versatile",
            )

            assert result == "Groq custom"

    @pytest.mark.asyncio
    async def test_generate_with_user_selected_model_openrouter(self, router):
        """Test generation with user-selected OpenRouter model."""
        with patch.object(
            router.openrouter, "generate", new=AsyncMock(return_value="OR response")
        ):
            result = await router.generate(
                prompt="Test",
                user_selected_model="meta-llama/llama-3.1-8b-instruct:free",
            )

            assert result == "OR response"

    @pytest.mark.asyncio
    async def test_generate_with_user_selected_model_openrouter_non_free(self, router):
        """Test non-free OpenRouter model is downgraded."""
        with patch.object(
            router.openrouter, "generate", new=AsyncMock(return_value="OR response")
        ) as mock_generate:
            result = await router.generate(
                prompt="Test",
                user_selected_model="openai/gpt-4o",
            )

            assert result == "OR response"
            assert (
                mock_generate.await_args.kwargs["model"]
                == "google/gemini-2.0-flash-exp:free"
            )
            assert router.free_tier_downgrades == 1

    @pytest.mark.asyncio
    async def test_generate_cloud_groq_rate_limit_fallback_to_openrouter(self, router):
        """Test fallback from Groq to OpenRouter on rate limit."""

        # Mock Groq to raise rate limit error
        async def groq_generate(*args, **kwargs):
            raise RateLimitError("Rate limit exceeded")

        with patch.object(router.groq_breaker, "call", side_effect=groq_generate):
            # Mock OpenRouter success
            with patch.object(
                router.openrouter,
                "generate",
                new=AsyncMock(return_value="OpenRouter response"),
            ):
                result = await router._generate_cloud(
                    prompt="Test",
                    max_tokens=100,
                    temperature=0.7,
                )

                assert result == "OpenRouter response"
                assert router.openrouter_requests == 1

    @pytest.mark.asyncio
    async def test_generate_cloud_openrouter_enforces_free_tier(
        self, router, mock_config
    ):
        """Test OpenRouter fallback enforces free-tier models."""
        mock_config.INFERENCE_FALLBACK_PROVIDER = "openrouter"
        mock_config.INFERENCE_DEFAULT_MODEL = "openai/gpt-4o"

        with patch.object(
            router.openrouter,
            "generate",
            new=AsyncMock(return_value="OpenRouter response"),
        ) as mock_generate:
            result = await router._generate_cloud(
                prompt="Test",
                max_tokens=100,
                temperature=0.7,
            )

            assert result == "OpenRouter response"
            assert (
                mock_generate.await_args.kwargs["model"]
                == "google/gemini-2.0-flash-exp:free"
            )
            assert router.free_tier_downgrades == 1

    @pytest.mark.asyncio
    async def test_check_ollama_health_success(self, router):
        """Test Ollama health check success."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            health = await router._check_ollama_health()
            assert health is True

    @pytest.mark.asyncio
    async def test_check_ollama_health_failure(self, router):
        """Test Ollama health check failure."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("Connection refused")
            )

            health = await router._check_ollama_health()
            assert health is False

    def test_estimate_tokens_tiktoken(self, router):
        """Test token estimation with tiktoken."""
        text = "This is a test sentence with multiple words."
        tokens = router._estimate_tokens(text)

        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_fallback(self, router, monkeypatch):
        """Test token estimation fallback."""

        def mock_get_encoding(name):
            raise Exception("tiktoken error")

        monkeypatch.setattr("tiktoken.get_encoding", mock_get_encoding)

        text = "A" * 400
        tokens = router._estimate_tokens(text)

        # Fallback: 1 token = 4 characters
        assert tokens == 100

    def test_get_metrics(self, router):
        """Test metrics retrieval."""
        metrics = router.get_metrics()

        assert "requests_total" in metrics
        assert "ollama_requests" in metrics
        assert "groq_requests" in metrics
        assert "openrouter_requests" in metrics
        assert "fallback_count" in metrics
        assert "free_tier_downgrades" in metrics
        assert "fallback_rate" in metrics
        assert "oom_errors" in metrics
        assert "groq_circuit_breaker" in metrics
        assert "openrouter_circuit_breaker" in metrics

    def test_get_metrics_with_data(self, router):
        """Test metrics after some requests."""
        router.requests_total = 10
        router.ollama_requests = 7
        router.groq_requests = 2
        router.openrouter_requests = 1
        router.fallback_count = 3
        router.oom_errors = 1

        metrics = router.get_metrics()

        assert metrics["requests_total"] == 10
        assert metrics["ollama_requests"] == 7
        assert metrics["groq_requests"] == 2
        assert metrics["openrouter_requests"] == 1
        assert metrics["fallback_count"] == 3
        assert metrics["fallback_rate"] == 0.3
        assert metrics["oom_errors"] == 1

    def test_get_metrics_zero_requests(self, router):
        """Test metrics when no requests have been made."""
        metrics = router.get_metrics()

        assert metrics["requests_total"] == 0
        assert metrics["fallback_rate"] == 0

    @pytest.mark.asyncio
    async def test_oom_error_detection_various_messages(self, router):
        """Test OOM error detection with various error messages."""
        router.mode = "local-only"

        # Test "out of memory" message
        router.ollama.generate.side_effect = Exception("model out of memory")

        with pytest.raises(OOMError):
            await router._generate_ollama("Test", 100, 0.7)

        # Test "oom" message
        router.ollama.generate.side_effect = Exception("OOM error occurred")

        with pytest.raises(OOMError):
            await router._generate_ollama("Test", 100, 0.7)

    @pytest.mark.asyncio
    async def test_non_oom_error_propagates(self, router):
        """Test that non-OOM errors are propagated."""
        router.mode = "local-only"
        router.ollama.generate.side_effect = Exception("Network error")

        with pytest.raises(Exception) as exc_info:
            await router._generate_ollama("Test", 100, 0.7)

        assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, router):
        """Test circuit breaker integration with cloud providers."""
        # This test verifies that circuit breakers are initialized
        assert router.groq_breaker is not None
        assert router.openrouter_breaker is not None
        assert router.groq_breaker.name == "groq"
        assert router.openrouter_breaker.name == "openrouter"
        assert router.groq_breaker.cooldown_seconds == 60
        assert router.openrouter_breaker.cooldown_seconds == 60

    @pytest.mark.asyncio
    async def test_all_providers_fail(self, router):
        """Test error handling when all providers fail."""
        router.mode = "cloud-only"

        # Mock both providers to fail
        async def groq_fail(*args, **kwargs):
            raise RateLimitError("Groq rate limit")

        with patch.object(router.groq_breaker, "call", side_effect=groq_fail):
            with patch.object(
                router.openrouter,
                "generate",
                new=AsyncMock(side_effect=Exception("OR error")),
            ):
                with pytest.raises(Exception) as exc_info:
                    await router._generate_cloud("Test", 100, 0.7)

                assert "OR error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_openrouter_preferred_when_configured(self, router, mock_config):
        """Test OpenRouter is used when configured as preferred provider."""
        mock_config.INFERENCE_FALLBACK_PROVIDER = "openrouter"

        with patch.object(
            router.openrouter,
            "generate",
            new=AsyncMock(return_value="OpenRouter response"),
        ):
            result = await router._generate_cloud("Test", 100, 0.7)

            assert result == "OpenRouter response"
            assert router.openrouter_requests == 1
            # Groq should not be called when OpenRouter is preferred
            assert router.groq_requests == 0
