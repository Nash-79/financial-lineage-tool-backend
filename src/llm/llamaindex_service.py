"""
LlamaIndex RAG Service for Financial Lineage Tool

This service integrates LlamaIndex with local Ollama for:
- Document indexing (SQL files, entities)
- Vector storage (Qdrant)
- RAG query execution
- Embedding generation with caching
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import hashlib

from llama_index.core import (
    VectorStoreIndex,
    Document,
    Settings,
    StorageContext,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient

logger = logging.getLogger(__name__)


@dataclass
class RAGMetrics:
    """Metrics for RAG operations"""

    embedding_cache_hits: int = 0
    embedding_cache_misses: int = 0
    query_cache_hits: int = 0
    query_cache_misses: int = 0
    total_queries: int = 0
    avg_retrieval_latency_ms: float = 0.0
    avg_generation_latency_ms: float = 0.0


class LlamaIndexService:
    """
    Service for LlamaIndex RAG operations with local Ollama and Qdrant.

    Features:
    - Document indexing with semantic chunking
    - Vector search with metadata filtering
    - RAG query with context retrieval
    - Redis caching for embeddings and queries
    - Comprehensive metrics tracking
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        llm_model: str = "llama3.1:8b",
        embedding_model: str = "nomic-embed-text",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "code_chunks",
        redis_client=None,  # Optional Redis client for caching
    ):
        """
        Initialize LlamaIndex service.

        Args:
            ollama_host: Ollama API URL (host.docker.internal:11434 in Docker)
            llm_model: Ollama model for chat completion
            embedding_model: Ollama model for embeddings (768-dimensional)
            qdrant_host: Qdrant host
            qdrant_port: Qdrant port
            collection_name: Qdrant collection name
            redis_client: Optional Redis client for caching
        """
        self.ollama_host = ollama_host
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        self.redis_client = redis_client
        self.metrics = RAGMetrics()

        # Initialize Ollama LLM
        logger.info(f"Initializing Ollama LLM with model: {llm_model}")
        self.llm = Ollama(
            model=llm_model,
            base_url=ollama_host,
            temperature=0.1,
            request_timeout=120.0,
        )

        # Initialize Ollama Embeddings
        logger.info(f"Initializing Ollama embeddings with model: {embedding_model}")
        self.embed_model = OllamaEmbedding(
            model_name=embedding_model,
            base_url=ollama_host,
        )

        # Initialize Qdrant clients (both sync and async)
        logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}")
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.async_qdrant_client = AsyncQdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize Qdrant vector store with async client for query operations
        self.vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            aclient=self.async_qdrant_client,
            collection_name=collection_name,
        )

        # Configure LlamaIndex global settings
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50

        # Storage context
        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )

        # Query engine (initialized lazily)
        self._query_engine = None

        logger.info("LlamaIndex service initialized successfully")

    async def check_ollama_connectivity(self) -> bool:
        """
        Check if Ollama is accessible and required models are available.

        Returns:
            True if Ollama is accessible and models are available

        Raises:
            ConnectionError: If Ollama is not accessible
            ValueError: If required models are missing
        """
        try:
            # Try to list models to check connectivity
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.ollama_host}/api/tags")
                response.raise_for_status()

                models_data = response.json()
                available_models = [m["name"] for m in models_data.get("models", [])]

                # Check required models (handle :latest tag variations)
                required_models = [self.llm_model, self.embedding_model]

                def is_model_available(required: str, available: List[str]) -> bool:
                    """Check if a model is available, handling :latest tag variations."""
                    # Direct match
                    if required in available:
                        return True
                    # Check if required+':latest' matches
                    if f"{required}:latest" in available:
                        return True
                    # Check if any available model starts with required name
                    for avail in available:
                        if avail.startswith(f"{required}:"):
                            return True
                    return False

                missing_models = [
                    m
                    for m in required_models
                    if not is_model_available(m, available_models)
                ]

                if missing_models:
                    error_msg = (
                        f"Required Ollama models not found: {missing_models}\n"
                        f"Please pull them with:\n"
                    )
                    for model in missing_models:
                        error_msg += f"  ollama pull {model}\n"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                logger.info(
                    f"✓ Ollama connectivity verified. Available models: {available_models}"
                )
                return True

        except httpx.RequestError as e:
            error_msg = (
                f"Failed to connect to Ollama at {self.ollama_host}\n"
                f"Error: {e}\n"
                f"Troubleshooting:\n"
                f"  1. Check if Ollama is running: ollama list\n"
                f"  2. If in Docker, ensure host.docker.internal is accessible\n"
                f"  3. Check firewall settings\n"
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg)

    async def index_documents(
        self,
        documents: List[Document],
        show_progress: bool = True,
    ) -> VectorStoreIndex:
        """
        Index documents into Qdrant vector store using LlamaIndex.

        Args:
            documents: List of LlamaIndex Document objects with text and metadata
            show_progress: Whether to show progress bar

        Returns:
            VectorStoreIndex for querying
        """
        logger.info(f"Indexing {len(documents)} documents...")

        # Create index from documents
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=self.storage_context,
            show_progress=show_progress,
        )

        logger.info(f"✓ Successfully indexed {len(documents)} documents")
        return index

    async def index_code_chunks(
        self,
        chunks: List[Any],  # List of CodeChunk objects
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Index code chunks into Qdrant using LlamaIndex.

        Args:
            chunks: List of CodeChunk objects from semantic_chunker
            batch_size: Number of chunks to process in each batch

        Returns:
            Dict with indexing statistics
        """
        from llama_index.core import Document

        logger.info(f"Converting {len(chunks)} code chunks to LlamaIndex documents...")

        # Convert CodeChunk objects to LlamaIndex Documents
        documents = []
        for chunk in chunks:
            # Use the chunk's to_embedding_text() method for optimal embedding
            doc = Document(
                text=chunk.to_embedding_text(),
                metadata={
                    "file_path": str(chunk.file_path),
                    "chunk_type": chunk.chunk_type.value,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": chunk.language,
                    "tables": chunk.tables_referenced,
                    "columns": chunk.columns_referenced,
                    "functions": chunk.functions_defined,
                    "dependencies": chunk.dependencies,
                    "token_count": chunk.token_count,
                },
                excluded_llm_metadata_keys=["token_count"],  # Don't send to LLM
                excluded_embed_metadata_keys=["token_count"],  # Don't embed this
            )
            documents.append(doc)

        # Index in batches to avoid memory issues
        total_indexed = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            await self.index_documents(batch, show_progress=False)
            total_indexed += len(batch)
            logger.info(f"Indexed {total_indexed}/{len(documents)} documents")

        return {
            "total_chunks": len(chunks),
            "total_documents": len(documents),
            "status": "success",
        }

    def get_query_engine(
        self,
        similarity_top_k: int = 5,
        response_mode: str = "compact",
    ):
        """
        Get or create query engine for RAG.

        Args:
            similarity_top_k: Number of similar chunks to retrieve
            response_mode: Response synthesis mode ("compact", "tree_summarize", etc.)

        Returns:
            Query engine for RAG queries
        """
        if self._query_engine is None:
            # Create index from existing vector store
            index = VectorStoreIndex.from_vector_store(
                self.vector_store,
                storage_context=self.storage_context,
            )

            # Create query engine
            self._query_engine = index.as_query_engine(
                similarity_top_k=similarity_top_k,
                response_mode=response_mode,
            )

            logger.info(
                f"Query engine created (top_k={similarity_top_k}, mode={response_mode})"
            )

        return self._query_engine

    async def query(
        self,
        question: str,
        similarity_top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute RAG query with context retrieval.

        Args:
            question: User's question
            similarity_top_k: Number of similar chunks to retrieve
            metadata_filters: Optional filters for metadata (e.g., {"file_path": "..."})

        Returns:
            Dict with response, sources, and metadata
        """
        import time

        self.metrics.total_queries += 1

        # Check cache first
        cache_key = self._get_query_cache_key(question, metadata_filters)
        if self.redis_client:
            cached_result = await self._get_cached_query(cache_key)
            if cached_result:
                self.metrics.query_cache_hits += 1
                logger.info(f"✓ Cache hit for query: {question[:50]}...")
                return cached_result
            self.metrics.query_cache_misses += 1

        # Execute query
        start_time = time.time()

        query_engine = self.get_query_engine(similarity_top_k=similarity_top_k)
        response = await query_engine.aquery(question)

        query_latency_ms = (time.time() - start_time) * 1000

        # Extract sources
        sources = []
        if hasattr(response, "source_nodes"):
            for node in response.source_nodes:
                sources.append(
                    {
                        "text": (
                            node.text[:200] + "..."
                            if len(node.text) > 200
                            else node.text
                        ),
                        "metadata": node.metadata,
                        "score": node.score,
                    }
                )

        result = {
            "response": str(response),
            "sources": sources,
            "query_latency_ms": query_latency_ms,
            "num_sources": len(sources),
        }

        # Cache result
        if self.redis_client:
            await self._cache_query_result(cache_key, result, ttl_seconds=3600)

        # Update metrics
        self._update_query_metrics(query_latency_ms)

        logger.info(
            f"✓ Query executed in {query_latency_ms:.2f}ms with {len(sources)} sources"
        )
        return result

    def _get_query_cache_key(
        self, question: str, metadata_filters: Optional[Dict] = None
    ) -> str:
        """Generate cache key for query."""
        key_data = f"{question}:{metadata_filters}"
        return f"query:{hashlib.sha256(key_data.encode()).hexdigest()}"

    async def _get_cached_query(self, cache_key: str) -> Optional[Dict]:
        """Get cached query result from Redis."""
        if not self.redis_client:
            return None
        try:
            import json

            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        return None

    async def _cache_query_result(
        self, cache_key: str, result: Dict, ttl_seconds: int = 3600
    ):
        """Cache query result in Redis."""
        if not self.redis_client:
            return
        try:
            import json

            await self.redis_client.setex(cache_key, ttl_seconds, json.dumps(result))
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def _update_query_metrics(self, query_latency_ms: float):
        """Update query metrics with exponential moving average."""
        alpha = 0.3  # Smoothing factor
        if self.metrics.avg_generation_latency_ms == 0:
            self.metrics.avg_generation_latency_ms = query_latency_ms
        else:
            self.metrics.avg_generation_latency_ms = (
                alpha * query_latency_ms
                + (1 - alpha) * self.metrics.avg_generation_latency_ms
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current RAG metrics.

        Returns:
            Dictionary of metrics
        """
        total_embedding_requests = (
            self.metrics.embedding_cache_hits + self.metrics.embedding_cache_misses
        )
        total_query_requests = (
            self.metrics.query_cache_hits + self.metrics.query_cache_misses
        )

        return {
            "total_queries": self.metrics.total_queries,
            "embedding_cache_hit_rate": (
                self.metrics.embedding_cache_hits / total_embedding_requests
                if total_embedding_requests > 0
                else 0
            ),
            "query_cache_hit_rate": (
                self.metrics.query_cache_hits / total_query_requests
                if total_query_requests > 0
                else 0
            ),
            "avg_query_latency_ms": self.metrics.avg_generation_latency_ms,
            "mode": "llamaindex",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of LlamaIndex service.

        Returns:
            Dictionary with health status
        """
        status = {
            "llamaindex": "unknown",
            "ollama": "unknown",
            "qdrant": "unknown",
            "details": {},
        }

        # Check Ollama
        try:
            await self.check_ollama_connectivity()
            status["ollama"] = "healthy"
        except Exception as e:
            status["ollama"] = "degraded"
            status["details"]["ollama_error"] = str(e)

        # Check Qdrant
        try:
            collections = self.qdrant_client.get_collections()
            status["qdrant"] = "healthy"
            status["details"]["qdrant_collections"] = len(collections.collections)
        except Exception as e:
            status["qdrant"] = "degraded"
            status["details"]["qdrant_error"] = str(e)

        # Overall status
        if status["ollama"] == "healthy" and status["qdrant"] == "healthy":
            status["llamaindex"] = "healthy"
        else:
            status["llamaindex"] = "degraded"

        return status
