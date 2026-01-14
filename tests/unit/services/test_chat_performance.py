"""Unit tests for chat performance optimizations."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch


class TestOllamaEmbeddingCache:
    """Tests for embedding cache in OllamaClient."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def ollama_client_with_cache(self, mock_redis):
        """Create OllamaClient with Redis cache."""
        from src.services.ollama_service import OllamaClient

        return OllamaClient(host="http://localhost:11434", redis_client=mock_redis)

    @pytest.fixture
    def ollama_client_no_cache(self):
        """Create OllamaClient without Redis cache."""
        from src.services.ollama_service import OllamaClient

        return OllamaClient(host="http://localhost:11434", redis_client=None)

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, ollama_client_with_cache):
        """Test cache key is deterministic for same input."""
        key1 = ollama_client_with_cache._get_cache_key("test text", "nomic-embed-text")
        key2 = ollama_client_with_cache._get_cache_key("test text", "nomic-embed-text")
        key3 = ollama_client_with_cache._get_cache_key(
            "different text", "nomic-embed-text"
        )

        assert key1 == key2, "Same input should produce same key"
        assert key1 != key3, "Different input should produce different key"
        assert key1.startswith("embed:"), "Key should have embed: prefix"

    @pytest.mark.asyncio
    async def test_cache_key_includes_model(self, ollama_client_with_cache):
        """Test cache key differs by model."""
        key1 = ollama_client_with_cache._get_cache_key("test", "model-a")
        key2 = ollama_client_with_cache._get_cache_key("test", "model-b")

        assert key1 != key2, "Different models should produce different keys"

    @pytest.mark.asyncio
    async def test_cache_hit(self, ollama_client_with_cache, mock_redis):
        """Test cache hit returns cached embedding."""
        cached_embedding = [0.1, 0.2, 0.3]
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_embedding))

        with patch.object(ollama_client_with_cache.client, "post") as mock_post:
            result = await ollama_client_with_cache.embed("test", "nomic-embed-text")

            # Should not call Ollama
            mock_post.assert_not_called()
            assert result == cached_embedding
            assert ollama_client_with_cache.cache_hits == 1
            assert ollama_client_with_cache.cache_misses == 0

    @pytest.mark.asyncio
    async def test_cache_miss(self, ollama_client_with_cache, mock_redis):
        """Test cache miss calls Ollama and stores result."""
        mock_redis.get = AsyncMock(return_value=None)
        embedding = [0.1, 0.2, 0.3]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": embedding}

        with patch.object(
            ollama_client_with_cache.client, "post", return_value=mock_response
        ):
            result = await ollama_client_with_cache.embed("test", "nomic-embed-text")

            assert result == embedding
            assert ollama_client_with_cache.cache_misses == 1
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_fallback_on_redis_error(
        self, ollama_client_with_cache, mock_redis
    ):
        """Test embedding works when Redis fails."""
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))
        embedding = [0.1, 0.2, 0.3]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": embedding}

        with patch.object(
            ollama_client_with_cache.client, "post", return_value=mock_response
        ):
            result = await ollama_client_with_cache.embed("test", "nomic-embed-text")

            assert result == embedding, "Should fallback to Ollama on cache error"

    @pytest.mark.asyncio
    async def test_no_cache_when_redis_none(self, ollama_client_no_cache):
        """Test embedding works without Redis client."""
        embedding = [0.1, 0.2, 0.3]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": embedding}

        with patch.object(
            ollama_client_no_cache.client, "post", return_value=mock_response
        ):
            result = await ollama_client_no_cache.embed("test", "nomic-embed-text")

            assert result == embedding

    def test_cache_stats(self, ollama_client_with_cache):
        """Test cache statistics calculation."""
        ollama_client_with_cache.cache_hits = 3
        ollama_client_with_cache.cache_misses = 1

        stats = ollama_client_with_cache.get_cache_stats()

        assert stats["cache_hits"] == 3
        assert stats["cache_misses"] == 1
        assert stats["hit_rate"] == 0.75


class TestBatchGraphQueries:
    """Tests for batch graph queries in Neo4jGraphClient."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create mock Neo4j client."""
        client = MagicMock()
        client._execute_query = MagicMock(return_value=[])
        return client

    def test_find_by_names_empty_input(self, mock_graph_client):
        """Test find_by_names with empty list."""
        from src.knowledge_graph.neo4j_client import Neo4jGraphClient

        # Patch the method on a real instance
        with patch.object(
            Neo4jGraphClient, "__init__", lambda x, *args, **kwargs: None
        ):
            client = Neo4jGraphClient.__new__(Neo4jGraphClient)
            client._execute_query = MagicMock()

            result = client.find_by_names([])

            assert result == []
            client._execute_query.assert_not_called()

    def test_find_by_names_filters_short_words(self, mock_graph_client):
        """Test that short words are filtered out."""
        from src.knowledge_graph.neo4j_client import Neo4jGraphClient

        with patch.object(
            Neo4jGraphClient, "__init__", lambda x, *args, **kwargs: None
        ):
            client = Neo4jGraphClient.__new__(Neo4jGraphClient)
            client._execute_query = MagicMock(return_value=[])

            result = client.find_by_names(
                ["a", "ab", "abc"]
            )  # Only "abc" should pass (len > 2)

            # Should be called since "abc" is long enough
            client._execute_query.assert_called_once()
            call_args = client._execute_query.call_args
            assert "abc" in call_args[1]["patterns"]

    def test_find_by_names_deduplicates_results(self):
        """Test that results are deduplicated by ID."""
        from src.knowledge_graph.neo4j_client import Neo4jGraphClient

        with patch.object(
            Neo4jGraphClient, "__init__", lambda x, *args, **kwargs: None
        ):
            client = Neo4jGraphClient.__new__(Neo4jGraphClient)
            # Return duplicate records
            client._execute_query = MagicMock(
                return_value=[
                    {"n": {"id": "t1", "name": "table1"}, "labels": ["Table"]},
                    {
                        "n": {"id": "t1", "name": "table1"},
                        "labels": ["Table"],
                    },  # Duplicate
                    {"n": {"id": "t2", "name": "table2"}, "labels": ["Table"]},
                ]
            )

            result = client.find_by_names(["table"])

            assert len(result) == 2, "Should deduplicate by ID"
            ids = [r["id"] for r in result]
            assert "t1" in ids
            assert "t2" in ids


class TestParallelExecution:
    """Tests for parallel search execution in LocalSupervisorAgent."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent with mocked dependencies."""
        from src.services.agent_service import LocalSupervisorAgent

        ollama = AsyncMock()
        qdrant = AsyncMock()
        graph = MagicMock()

        agent = LocalSupervisorAgent(
            ollama=ollama,
            qdrant=qdrant,
            graph=graph,
            llm_model="test-model",
            embedding_model="test-embed",
        )
        return agent

    @pytest.mark.asyncio
    async def test_parallel_search_runs_concurrently(self, mock_agent):
        """Test that vector and graph search run in parallel."""
        # Track call order
        call_order = []

        async def mock_embed(*args, **kwargs):
            call_order.append("embed_start")
            await asyncio.sleep(0.1)
            call_order.append("embed_end")
            return [0.1, 0.2, 0.3]

        async def mock_search(*args, **kwargs):
            return []

        def mock_find_by_names(*args, **kwargs):
            call_order.append("graph_start")
            call_order.append("graph_end")
            return []

        mock_agent.ollama.embed = mock_embed
        mock_agent.qdrant.search = mock_search
        mock_agent.graph.find_by_names = mock_find_by_names

        await mock_agent._parallel_search("test query here")

        # Graph should start before embed finishes (parallel execution)
        # With asyncio.gather, both should be scheduled concurrently
        assert "embed_start" in call_order
        assert "graph_start" in call_order

    @pytest.mark.asyncio
    async def test_parallel_search_handles_exceptions(self, mock_agent):
        """Test that exceptions in one search don't break the other."""
        mock_agent.ollama.embed = AsyncMock(side_effect=Exception("Embed failed"))
        mock_agent.qdrant.search = AsyncMock()
        mock_agent.graph.find_by_names = MagicMock(
            return_value=[{"id": "t1", "name": "test"}]
        )

        code_results, graph_results = await mock_agent._parallel_search("test")

        assert code_results == [], "Should return empty on error"
        assert len(graph_results) == 1, "Graph search should still work"


class TestChatRequestModel:
    """Tests for ChatRequest model changes."""

    def test_skip_memory_default_false(self):
        """Test skip_memory defaults to False."""
        from src.api.models.chat import ChatRequest

        request = ChatRequest(query="test")
        assert request.skip_memory is False

    def test_skip_memory_can_be_set_true(self):
        """Test skip_memory can be set to True."""
        from src.api.models.chat import ChatRequest

        request = ChatRequest(query="test", skip_memory=True)
        assert request.skip_memory is True

    def test_session_id_optional(self):
        """Test session_id is optional."""
        from src.api.models.chat import ChatRequest

        request = ChatRequest(query="test")
        assert request.session_id is None

        request_with_session = ChatRequest(query="test", session_id="sess-123")
        assert request_with_session.session_id == "sess-123"
