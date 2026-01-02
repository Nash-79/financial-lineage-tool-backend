"""Chat endpoints for interactive queries."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException

from ..config import config
from ..models.chat import ChatRequest, ChatResponse

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_app_state() -> Any:
    """Get application state from FastAPI app.

    This is a placeholder that will be replaced with actual state injection.
    The state will be passed via dependency injection in main.py.
    """
    # This will be replaced with proper dependency injection
    from ..main_local import state

    return state


@router.post("/deep", response_model=ChatResponse)
async def chat_deep(request: ChatRequest) -> ChatResponse:
    """Deep analysis chat endpoint with comprehensive lineage analysis.

    Uses both vector search and graph traversal for detailed insights.
    Provides more context (top 10 results) for thorough analysis.

    Args:
        request: Chat request with query and optional context.

    Returns:
        ChatResponse with answer, sources, and latency metrics.

    Raises:
        HTTPException: If analysis fails or agent is not initialized.
    """
    state = get_app_state()
    start_time = time.time()

    try:
        if config.USE_LLAMAINDEX and state.llamaindex_service:
            # Use LlamaIndex RAG pipeline
            result = await state.llamaindex_service.query(
                question=request.query,
                similarity_top_k=10,  # More context for deep analysis
                metadata_filters=request.context,
            )
            return ChatResponse(
                response=result["response"],
                sources=result.get("sources", []),
                query_type="deep",
                latency_ms=result.get("query_latency_ms", 0),
            )
        else:
            # Use legacy agent
            if not state.agent:
                raise HTTPException(status_code=503, detail="Agent not initialized")

            result = await state.agent.query(request.query)
            latency_ms = (time.time() - start_time) * 1000

            return ChatResponse(
                response=result.get("answer", ""),
                sources=[{"text": s} for s in result.get("sources", [])],
                query_type="deep",
                latency_ms=latency_ms,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deep analysis failed: {e}")


@router.post("/semantic", response_model=ChatResponse)
async def chat_semantic(request: ChatRequest) -> ChatResponse:
    """Semantic search chat endpoint optimized for natural language understanding.

    Uses vector embeddings for similarity-based retrieval. Best for finding
    conceptually similar code or documentation.

    Args:
        request: Chat request with query and optional context.

    Returns:
        ChatResponse with answer, sources, and latency metrics.

    Raises:
        HTTPException: If semantic search fails.
    """
    state = get_app_state()
    start_time = time.time()

    try:
        if config.USE_LLAMAINDEX and state.llamaindex_service:
            result = await state.llamaindex_service.query(
                question=request.query,
                similarity_top_k=config.SIMILARITY_TOP_K,
                metadata_filters=request.context,
            )
            return ChatResponse(
                response=result["response"],
                sources=result.get("sources", []),
                query_type="semantic",
                latency_ms=result.get("query_latency_ms", 0),
            )
        else:
            # Use Qdrant direct search
            embedding = await state.ollama.embed(request.query)
            results = await state.qdrant.search("code_chunks", embedding, limit=5)

            # Generate response using LLM
            context = "\n\n".join(
                [r.get("payload", {}).get("text", "") for r in results]
            )
            prompt = f"Based on this context:\n\n{context}\n\nAnswer: {request.query}"
            response = await state.ollama.generate(prompt, model=config.LLM_MODEL)

            latency_ms = (time.time() - start_time) * 1000
            return ChatResponse(
                response=response,
                sources=[
                    {"text": r.get("payload", {}).get("text", "")[:200]}
                    for r in results
                ],
                query_type="semantic",
                latency_ms=latency_ms,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {e}")


@router.post("/graph", response_model=ChatResponse)
async def chat_graph(request: ChatRequest) -> ChatResponse:
    """Graph-based chat endpoint for relationship and lineage queries.

    Focuses on Neo4j graph traversal and entity relationships. Best for
    understanding data flow and dependencies.

    Args:
        request: Chat request with query and optional context.

    Returns:
        ChatResponse with graph-aware answer and statistics.

    Raises:
        HTTPException: If graph is not initialized or query fails.
    """
    state = get_app_state()
    start_time = time.time()

    try:
        if not state.graph:
            raise HTTPException(status_code=503, detail="Graph not initialized")

        # Simple graph-based query using Neo4j
        # Get graph stats as baseline
        stats = state.graph.get_stats()

        # Use LLM to generate graph-aware response
        system_prompt = f"""You are a data lineage assistant with access to a knowledge graph.
Current graph contains: {stats.get('nodes', 0)} nodes
Tables: {stats.get('Table', 0)}, Views: {stats.get('View', 0)}, Columns: {stats.get('Column', 0)}
"""
        response = await state.ollama.generate(
            prompt=request.query, model=config.LLM_MODEL, system=system_prompt
        )

        latency_ms = (time.time() - start_time) * 1000

        return ChatResponse(
            response=response,
            sources=[{"type": "graph_stats", "data": stats}],
            query_type="graph",
            latency_ms=latency_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph query failed: {e}")


@router.post("/text", response_model=ChatResponse)
async def chat_text(request: ChatRequest) -> ChatResponse:
    """Simple text-based chat endpoint for general questions.

    Minimal overhead, direct LLM interaction without heavy RAG.
    Best for general queries that don't require code context.

    Args:
        request: Chat request with query.

    Returns:
        ChatResponse with direct LLM answer.

    Raises:
        HTTPException: If text generation fails.
    """
    state = get_app_state()
    start_time = time.time()

    try:
        # Direct LLM call without RAG
        response = await state.ollama.generate(
            prompt=request.query,
            model=config.LLM_MODEL,
            system="You are a helpful assistant for data lineage and SQL schema analysis.",
        )

        latency_ms = (time.time() - start_time) * 1000

        return ChatResponse(
            response=response, sources=[], query_type="text", latency_ms=latency_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text chat failed: {e}")
