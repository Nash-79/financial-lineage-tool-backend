"""Chat endpoints for interactive queries."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

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
async def chat_deep(request: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    """Deep analysis chat endpoint with comprehensive lineage analysis.

    Uses both vector search and graph traversal for detailed insights.
    Provides more context (top 10 results) for thorough analysis.

    Args:
        request: Chat request with query and optional context.
        background_tasks: FastAPI background tasks handler.

    Returns:
        ChatResponse with answer, sources, and latency metrics.

    Raises:
        HTTPException: If analysis fails or agent is not initialized.
    """
    # Validate query is not empty
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

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
                model=config.LLM_MODEL,
            )
        else:
            # Use legacy agent
            if not state.agent:
                raise HTTPException(status_code=503, detail="Agent not initialized")

            # Retrieve memory context if session_id is available and not skipped
            memory_context = ""
            if request.session_id and state.memory and not request.skip_memory:
                try:
                    memory_context = await state.memory.retrieve_context(request.query, request.session_id)
                except Exception as e:
                    print(f"[!] Memory retrieval failed: {e}")

            result = await state.agent.query(request.query, memory_context=memory_context)
            
            # Store interaction asynchronously
            if request.session_id and state.memory:
                background_tasks.add_task(
                    state.memory.store_interaction,
                    request.session_id,
                    request.query,
                    result.get("answer", "")
                )

            latency_ms = (time.time() - start_time) * 1000

            return ChatResponse(
                response=result.get("answer", ""),
                sources=[{"text": s} for s in result.get("sources", [])],
                query_type="deep",
                latency_ms=latency_ms,
                model=config.LLM_MODEL,
                graph_data=result.get("graph_data"),
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
    # Validate query is not empty
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

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
                model=config.LLM_MODEL,
            )
        else:
            # Use Qdrant direct search
            embedding = await state.ollama.embed(request.query, config.EMBEDDING_MODEL)
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
                model=config.LLM_MODEL,
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
            model=config.LLM_MODEL,
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
            response=response, sources=[], query_type="text", latency_ms=latency_ms, model=config.LLM_MODEL
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deep/stream")
async def chat_deep_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """Streaming deep analysis chat endpoint using Server-Sent Events.

    Returns response tokens as they are generated for improved perceived latency.
    Uses the legacy RAG pipeline with streaming LLM generation.

    Note: LlamaIndex mode does not currently support streaming, so this endpoint
    always uses the legacy agent for retrieval + streaming Ollama for generation.

    Args:
        request: Chat request with query and optional context.
        background_tasks: FastAPI background tasks handler.

    Returns:
        StreamingResponse with SSE events containing response chunks.

    Raises:
        HTTPException: If analysis fails or agent is not initialized.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    state = get_app_state()

    # Streaming requires the legacy agent (LlamaIndex doesn't support streaming yet)
    if not state.agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def generate_sse():
        """Generator for SSE events."""
        start_time = time.time()

        try:
            # Step 1: Get context (same as /deep but we'll stream the LLM response)
            # Retrieve memory context if session_id is available and not skipped
            memory_context = ""
            if request.session_id and state.memory and not request.skip_memory:
                try:
                    memory_context = await state.memory.retrieve_context(
                        request.query, request.session_id
                    )
                except Exception as e:
                    print(f"[!] Memory retrieval failed: {e}")

            # Get search results using parallel search
            code_results, graph_results = await state.agent._parallel_search(request.query)
            lineage_info = state.agent._get_lineage_info(graph_results)

            # Build context
            context = ""
            if code_results:
                context += "## Relevant Code:\n\n"
                for result in code_results:
                    payload = result.get("payload", {})
                    context += f"File: {payload.get('file_path', 'unknown')}\n"
                    context += f"```sql\n{payload.get('content', '')[:1000]}\n```\n\n"

            if lineage_info:
                context += "## Knowledge Graph Results:\n\n"
                for info in lineage_info:
                    entity = info["entity"]
                    context += f"Entity: {entity.get('name')} ({entity.get('entity_type')})\n"
                    if info["upstream"]:
                        context += f"Upstream sources: {len(info['upstream'])} found\n"
                    if info["downstream"]:
                        context += f"Downstream targets: {len(info['downstream'])} found\n"
                    context += "\n"

            if not context:
                context = "No relevant code or graph data found."

            if memory_context:
                context = f"{memory_context}\n\n{context}"

            # Build prompt
            prompt = f"""Question: {request.query}

{context}

Based on the information above, answer the question about data lineage.
If there's no relevant data, explain what information would be needed."""

            # Step 2: Stream LLM response
            full_response = ""
            async for chunk in state.ollama.generate_stream(
                prompt=prompt,
                model=config.LLM_MODEL,
                system=state.agent.SYSTEM_PROMPT,
                temperature=0.1,
            ):
                full_response += chunk
                # Send SSE data event
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            # Step 3: Send final event with metadata
            latency_ms = (time.time() - start_time) * 1000
            graph_data = state.agent._build_graph_data(lineage_info) if lineage_info else {"nodes": [], "edges": []}

            final_data = {
                "type": "done",
                "sources": [
                    r.get("payload", {}).get("file_path")
                    for r in code_results
                    if r.get("payload")
                ],
                "graph_data": graph_data,
                "latency_ms": latency_ms,
                "model": config.LLM_MODEL,
            }
            yield f"data: {json.dumps(final_data)}\n\n"

            # Store interaction asynchronously
            if request.session_id and state.memory:
                background_tasks.add_task(
                    state.memory.store_interaction,
                    request.session_id,
                    request.query,
                    full_response,
                )

        except Exception as e:
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/title", response_model=Dict[str, str])
async def generate_title(request: ChatRequest) -> Dict[str, str]:
    """Generate a session title based on the first message.

    Args:
        request: Chat request containing the user's message.

    Returns:
        JSON with "title" field.
    """
    state = get_app_state()
    try:
        # Generate a descriptive title (15-30 characters as requested)
        prompt = (
            f"Generate a short descriptive title (15-30 characters) for a chat session starting with this query: "
            f"'{request.query}'. Do not use quotes."
        )
        title = await state.ollama.generate(
            prompt=prompt,
            model=config.LLM_MODEL,
        )
        return {"title": title.strip().replace('"', '').replace("'", "")}
    except Exception as e:
        # Fallback if title generation fails
        return {"title": request.query[:50]}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Delete chat session memory.

    Args:
        session_id: ID of the session to delete.
        background_tasks: FastAPI background tasks handler.

    Returns:
        Confirmation message.
    """
    state = get_app_state()
    if state.memory:
        background_tasks.add_task(state.memory.delete_session_memory, session_id)
        return {"status": "accepted", "message": f"Memory deletion scheduled for {session_id}"}
    
    return {"status": "ignored", "message": "Memory service not initialized"}
