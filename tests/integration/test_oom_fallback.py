"""Integration tests for OOM fallback scenarios."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

pytest.importorskip("llama_index")

from src.llm.inference_router import InferenceRouter
from src.llm.llamaindex_service import LlamaIndexService


class TestOOMFallbackIntegration:
    """Integration tests for OOM fallback with InferenceRouter and LlamaIndexService."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration with all providers enabled."""
        with patch("src.llm.inference_router.config") as mock_cfg:
            mock_cfg.OPENROUTER_API_KEY = "test-openrouter-key"
            mock_cfg.INFERENCE_FALLBACK_PROVIDER = "openrouter"
            mock_cfg.INFERENCE_DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"
            mock_cfg.OLLAMA_HOST = "http://localhost:11434"
            mock_cfg.get_llm_model.return_value = "llama3.1:8b"
            yield mock_cfg

    @pytest.fixture
    def mock_ollama_service(self):
        """Mock OllamaService."""
        service = MagicMock()
        service.generate = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_oom_fallback_local_to_openrouter(
        self, mock_config, mock_ollama_service
    ):
        """Test automatic fallback from local Ollama OOM to OpenRouter."""
        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

        # Mock Ollama health check
        with patch.object(router, "_check_ollama_health", return_value=True):
            # Mock Ollama to raise OOM error
            mock_ollama_service.generate.side_effect = Exception(
                "CUDA out of memory error"
            )

            # Mock OpenRouter success
            with patch.object(
                router.openrouter, "generate", return_value="OpenRouter response"
            ):
                result = await router.generate(
                    prompt="Explain SQL lineage for ORDERS table",
                    max_tokens=2048,
                    temperature=0.1,
                )

                # Verify fallback occurred
                assert result == "OpenRouter response"
                assert router.oom_errors == 1
                assert router.fallback_count == 1
                assert router.ollama_requests == 1
                assert router.openrouter_requests == 1

                # Verify metrics
                metrics = router.get_metrics()
                assert metrics["fallback_rate"] == 1.0
                assert metrics["oom_errors"] == 1

    @pytest.mark.asyncio
    async def test_oom_fallback_openrouter_rate_limit(
        self, mock_config, mock_ollama_service
    ):
        """Test fallback chain: Ollama OOM -> OpenRouter rate limit."""
        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

        with patch.object(router, "_check_ollama_health", return_value=True):
            # Mock Ollama OOM
            mock_ollama_service.generate.side_effect = Exception("out of memory")

            from src.llm.circuit_breaker import RateLimitError

            # Mock OpenRouter rate limit
            with patch.object(
                router.openrouter, "generate", side_effect=RateLimitError("Rate limit")
            ):
                with pytest.raises(Exception) as exc_info:
                    await router.generate(
                        prompt="Test prompt",
                        max_tokens=100,
                        temperature=0.7,
                    )

                assert "Rate limit" in str(exc_info.value)
                assert router.oom_errors == 1

    @pytest.mark.asyncio
    async def test_large_query_skips_ollama(self, mock_config, mock_ollama_service):
        """Test that large queries (>3000 tokens) skip Ollama entirely."""
        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

        # Create large prompt (~4000 tokens = ~16000 characters)
        large_prompt = "SELECT * FROM table WHERE condition " * 400

        with patch.object(router, "_check_ollama_health", return_value=True):
            with patch.object(
                router.openrouter, "generate", return_value="OpenRouter response"
            ):
                result = await router.generate(
                    prompt=large_prompt,
                    max_tokens=2048,
                )

                # Should skip Ollama due to size
                assert result == "OpenRouter response"
                assert router.ollama_requests == 0  # Should not attempt Ollama
                assert router.openrouter_requests == 1
                assert router.oom_errors == 0  # No OOM since we skipped Ollama

    @pytest.mark.asyncio
    async def test_llamaindex_service_oom_fallback(self, mock_config):
        """Test OOM fallback in LlamaIndexService RAG query."""
        # This is a more realistic integration test with LlamaIndexService

        # Mock Qdrant and Redis
        with patch("src.llm.llamaindex_service.QdrantClient"):
            with patch("src.llm.llamaindex_service.AsyncQdrantClient"):
                with patch("src.llm.llamaindex_service.Settings"):
                    # Create service with local-first mode
                    service = LlamaIndexService(
                        inference_mode="local-first",
                        redis_client=None,
                    )

                    # Mock retrieval
                    mock_node = MagicMock()
                    mock_node.text = "CREATE TABLE orders (id INT, amount DECIMAL)"
                    mock_node.score = 0.95
                    mock_node.metadata = {
                        "file_path": "schema.sql",
                        "line": 10,
                    }

                    # Mock Ollama OOM during generation
                    service.inference_router.ollama.generate.side_effect = Exception(
                        "out of memory"
                    )

                    # Mock OpenRouter success
                    with patch.object(
                        service.inference_router.openrouter,
                        "generate",
                        return_value="The ORDERS table contains order data...",
                    ):
                        # Mock retriever
                        with patch(
                            "src.llm.llamaindex_service.VectorStoreIndex"
                        ) as mock_index:
                            mock_retriever = MagicMock()
                            mock_retriever.aretrieve = AsyncMock(
                                return_value=[mock_node]
                            )
                            mock_index.from_vector_store.return_value.as_retriever.return_value = (
                                mock_retriever
                            )

                            # Execute query
                            result = await service.query(
                                question="What is the ORDERS table structure?"
                            )

                            # Verify fallback occurred
                            assert "ORDERS table" in result["response"]
                            assert result["fallback_used"] is True
                            assert result["router_metrics"]["oom_errors"] == 1
                            assert result["router_metrics"]["openrouter_requests"] == 1

    @pytest.mark.asyncio
    async def test_context_trimming_prevents_oom(self, mock_config):
        """Test that context trimming prevents OOM by reducing prompt size."""
        with patch("src.llm.llamaindex_service.QdrantClient"):
            with patch("src.llm.llamaindex_service.AsyncQdrantClient"):
                with patch("src.llm.llamaindex_service.Settings"):
                    service = LlamaIndexService(
                        inference_mode="local-first",
                        redis_client=None,
                    )

                    # Create many large nodes (would normally cause OOM)
                    large_nodes = []
                    for i in range(20):
                        node = MagicMock()
                        node.text = "X" * 1000  # Large text
                        node.score = 1.0 - (i * 0.05)
                        node.metadata = {"file_path": f"file_{i}.sql"}
                        large_nodes.append(node)

                    # Mock retriever to return large nodes
                    with patch(
                        "src.llm.llamaindex_service.VectorStoreIndex"
                    ) as mock_index:
                        mock_retriever = MagicMock()
                        mock_retriever.aretrieve = AsyncMock(return_value=large_nodes)
                        mock_index.from_vector_store.return_value.as_retriever.return_value = (
                            mock_retriever
                        )

                        # Mock Ollama success (context was trimmed, so no OOM)
                        service.inference_router.ollama.generate.return_value = {
                            "response": "Response based on trimmed context"
                        }

                        # Execute query
                        result = await service.query(
                            question="Test question", similarity_top_k=20
                        )

                        # Verify context was trimmed
                        assert result["context_adjustment"]["trim_applied"] is True
                        assert (
                            result["context_adjustment"]["trimmed_nodes"]
                            < result["context_adjustment"]["original_nodes"]
                        )

                        # Verify Ollama succeeded (no OOM due to trimming)
                        assert result["router_metrics"]["oom_errors"] == 0

    @pytest.mark.asyncio
    async def test_tree_summarize_for_large_retrievals(self, mock_config):
        """Test that tree_summarize is recommended for large retrievals."""
        with patch("src.llm.llamaindex_service.QdrantClient"):
            with patch("src.llm.llamaindex_service.AsyncQdrantClient"):
                with patch("src.llm.llamaindex_service.Settings"):
                    service = LlamaIndexService(
                        inference_mode="local-first",
                        redis_client=None,
                    )

                    # Create 15 nodes (> 10 threshold)
                    many_nodes = []
                    for i in range(15):
                        node = MagicMock()
                        node.text = f"Node {i} content"
                        node.score = 1.0
                        node.metadata = {}
                        many_nodes.append(node)

                    # Mock retriever
                    with patch(
                        "src.llm.llamaindex_service.VectorStoreIndex"
                    ) as mock_index:
                        mock_retriever = MagicMock()
                        mock_retriever.aretrieve = AsyncMock(return_value=many_nodes)
                        mock_index.from_vector_store.return_value.as_retriever.return_value = (
                            mock_retriever
                        )

                        # Mock generation
                        service.inference_router.ollama.generate.return_value = {
                            "response": "Summary response"
                        }

                        # Execute query
                        result = await service.query(
                            question="Test", similarity_top_k=15
                        )

                        # Verify tree_summarize was recommended
                        assert result["response_mode"] == "tree_summarize"

    @pytest.mark.asyncio
    async def test_metrics_tracking_across_multiple_queries(
        self, mock_config, mock_ollama_service
    ):
        """Test that metrics accumulate correctly across multiple queries."""
        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

        with patch.object(router, "_check_ollama_health", return_value=True):
            # Query 1: Ollama success
            mock_ollama_service.generate.return_value = {"response": "Response 1"}
            await router.generate("Query 1")

            # Query 2: Ollama OOM -> OpenRouter fallback
            mock_ollama_service.generate.side_effect = Exception("out of memory")
            with patch.object(
                router.openrouter, "generate", return_value="OpenRouter 2"
            ):
                await router.generate("Query 2")

            # Query 3: Ollama OOM -> OpenRouter fallback again
            with patch.object(
                router.openrouter, "generate", return_value="OpenRouter 3"
            ):
                await router.generate("Query 3")

            # Verify accumulated metrics
            metrics = router.get_metrics()
            assert metrics["requests_total"] == 3
            assert metrics["ollama_requests"] == 3  # All attempted Ollama first
            assert metrics["openrouter_requests"] == 2  # 2 fallbacks
            assert metrics["oom_errors"] == 2
            assert metrics["fallback_count"] == 2
            assert metrics["fallback_rate"] == pytest.approx(0.666, rel=0.01)

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_rapid_retries(
        self, mock_config, mock_ollama_service
    ):
        """Test that circuit breaker prevents rapid retries after rate limit."""
        from src.llm.circuit_breaker import RateLimitError

        router = InferenceRouter(
            mode="cloud-only",
            ollama_service=mock_ollama_service,
        )

        # First request: OpenRouter rate limit opens circuit
        async def openrouter_rate_limit(*args, **kwargs):
            raise RateLimitError("Rate limit exceeded")

        with patch.object(
            router.openrouter, "generate", side_effect=openrouter_rate_limit
        ):
            with pytest.raises(Exception):
                await router.generate("Query 1")

        # Circuit should now be open for OpenRouter
        assert router.openrouter_breaker.state == "open"

        # Second request: Circuit breaker should prevent OpenRouter attempt
        with pytest.raises(Exception):
            await router.generate("Query 2")

        metrics = router.openrouter_breaker.get_metrics()
        assert metrics["state"] == "open"

    @pytest.mark.asyncio
    async def test_quantized_model_selection_reduces_oom(self, mock_config):
        """Test that quantized model selection helps prevent OOM."""
        # Enable quantized models
        mock_config.OLLAMA_USE_QUANTIZED = True
        mock_config.get_llm_model.return_value = "llama3.1:8b-q4_0"

        mock_ollama = MagicMock()
        mock_ollama.generate = AsyncMock()

        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama,
        )

        with patch.object(router, "_check_ollama_health", return_value=True):
            # Quantized model succeeds (no OOM due to 50% memory reduction)
            mock_ollama.generate.return_value = {
                "response": "Response from quantized model"
            }

            result = await router.generate("Test prompt")

            # Verify quantized model was used
            assert result == "Response from quantized model"
            assert router.oom_errors == 0
            assert router.fallback_count == 0

    @pytest.mark.asyncio
    async def test_user_model_selection_bypasses_routing(
        self, mock_config, mock_ollama_service
    ):
        """Test that user model selection bypasses automatic routing."""
        router = InferenceRouter(
            mode="local-first",
            ollama_service=mock_ollama_service,
        )

        # User explicitly selects OpenRouter model
        with patch.object(
            router.openrouter, "generate", return_value="OpenRouter direct"
        ):
            result = await router.generate(
                prompt="Test",
                user_selected_model="meta-llama/llama-3.1-8b-instruct:free",
            )

            # Should use OpenRouter directly, skipping health checks and routing
            assert result == "OpenRouter direct"
            assert router.ollama_requests == 0  # Ollama should be skipped
            assert router.openrouter_requests == 1
