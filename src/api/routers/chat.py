"""Chat endpoints for interactive queries."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import config
from ..middleware.auth import User, get_current_user
from ..models.chat import (
    ChatRequest,
    ChatResponse,
    ChatGraphArtifactResponse,
    ChatGraphArtifactNotFoundResponse,
)
from src.services.chat_service import AllModelsFailed
from src.storage.duckdb_client import get_duckdb_client
from src.utils.audit_logger import get_audit_logger

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


async def _run_chat(
    *,
    endpoint: str,
    request: ChatRequest,
    user: User,
    background_tasks: Optional[BackgroundTasks] = None,
) -> ChatResponse:
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    state = get_app_state()
    if not state.chat_service:
        raise HTTPException(status_code=503, detail="Chat service not initialized")

    memory_context = ""
    if endpoint == "deep" and request.session_id and state.memory and not request.skip_memory:
        try:
            memory_context = await state.memory.retrieve_context(
                request.query, request.session_id
            )
        except Exception as exc:
            print(f"[!] Memory retrieval failed: {exc}")

    start_time = time.time()
    try:
        result = await state.chat_service.generate(
            endpoint=endpoint,
            query=request.query,
            context=request.context,
            memory_context=memory_context,
        )
    except AllModelsFailed as exc:
        payload = {
            "error": "All free-tier models exhausted for this endpoint",
            "endpoint": f"/api/chat/{endpoint}",
            "attempts": [
                {
                    "model": attempt.model,
                    "error": attempt.error,
                    "timestamp": attempt.timestamp,
                }
                for attempt in exc.attempts
            ],
            "retry_after": exc.retry_after,
        }
        return JSONResponse(status_code=503, content=payload)  # type: ignore[return-value]

    latency_ms = (time.time() - start_time) * 1000

    if endpoint == "deep" and request.session_id and state.memory and background_tasks:
        background_tasks.add_task(
            state.memory.store_interaction,
            request.session_id,
            request.query,
            result.get("response", ""),
        )

    # Generate message_id and persist graph_data if present and session_id is provided
    message_id = None
    graph_data = result.get("graph_data")
    if graph_data and request.session_id and background_tasks:
        message_id = str(uuid.uuid4())
        background_tasks.add_task(
            _persist_graph_artifact,
            request.session_id,
            message_id,
            graph_data,
        )

    return ChatResponse(
        response=result.get("response", ""),
        sources=result.get("sources", []),
        query_type=endpoint,
        latency_ms=latency_ms,
        model=result.get("model"),
        next_actions=result.get("next_actions", []),
        warnings=result.get("warnings", []),
        graph_data=graph_data,
        message_id=message_id,
    )


async def _persist_graph_artifact(
    session_id: str,
    message_id: str,
    graph_data: Dict[str, Any],
) -> None:
    """Persist graph data as a chat artifact in DuckDB."""
    try:
        duckdb = get_duckdb_client()
        await duckdb.store_chat_artifact(
            session_id=session_id,
            message_id=message_id,
            artifact_type="graph",
            data=graph_data,
        )
    except Exception as exc:
        # Log but don't fail the request - persistence is best-effort
        print(f"[!] Failed to persist graph artifact: {exc}")


@router.post("/deep", response_model=ChatResponse)
async def chat_deep(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """Deep analysis chat endpoint with comprehensive lineage analysis."""
    audit = get_audit_logger()
    start_time = time.time()
    try:
        return await _run_chat(
            endpoint="deep",
            request=request,
            user=user,
            background_tasks=background_tasks,
        )
    finally:
        try:
            latency_ms = (time.time() - start_time) * 1000
            audit.log_query(
                user_id=user.user_id,
                query_type="chat",
                query_hash=hashlib.sha256(request.query.encode()).hexdigest(),
                latency_ms=latency_ms,
            )
        except Exception:
            pass


@router.post("/semantic", response_model=ChatResponse)
async def chat_semantic(
    request: ChatRequest, user: User = Depends(get_current_user)
) -> ChatResponse:
    """Semantic search chat endpoint optimized for natural language understanding."""
    audit = get_audit_logger()
    start_time = time.time()
    try:
        return await _run_chat(endpoint="semantic", request=request, user=user)
    finally:
        try:
            latency_ms = (time.time() - start_time) * 1000
            audit.log_query(
                user_id=user.user_id,
                query_type="chat",
                query_hash=hashlib.sha256(request.query.encode()).hexdigest(),
                latency_ms=latency_ms,
            )
        except Exception:
            pass


@router.post("/graph", response_model=ChatResponse)
async def chat_graph(
    request: ChatRequest, user: User = Depends(get_current_user)
) -> ChatResponse:
    """Graph-based chat endpoint for relationship and lineage queries."""
    audit = get_audit_logger()
    start_time = time.time()
    try:
        return await _run_chat(endpoint="graph", request=request, user=user)
    finally:
        try:
            latency_ms = (time.time() - start_time) * 1000
            audit.log_query(
                user_id=user.user_id,
                query_type="chat",
                query_hash=hashlib.sha256(request.query.encode()).hexdigest(),
                latency_ms=latency_ms,
            )
        except Exception:
            pass


@router.post("/text", response_model=ChatResponse)
async def chat_text(
    request: ChatRequest, user: User = Depends(get_current_user)
) -> ChatResponse:
    """Simple text-based chat endpoint for general questions."""
    audit = get_audit_logger()
    start_time = time.time()
    try:
        return await _run_chat(endpoint="text", request=request, user=user)
    finally:
        try:
            latency_ms = (time.time() - start_time) * 1000
            audit.log_query(
                user_id=user.user_id,
                query_type="chat",
                query_hash=hashlib.sha256(request.query.encode()).hexdigest(),
                latency_ms=latency_ms,
            )
        except Exception:
            pass


@router.post("/title", response_model=ChatResponse)
async def chat_title(
    request: ChatRequest, user: User = Depends(get_current_user)
) -> ChatResponse:
    """Generate a session title based on the first message."""
    audit = get_audit_logger()
    start_time = time.time()
    try:
        return await _run_chat(endpoint="title", request=request, user=user)
    finally:
        try:
            latency_ms = (time.time() - start_time) * 1000
            audit.log_query(
                user_id=user.user_id,
                query_type="chat",
                query_hash=hashlib.sha256(request.query.encode()).hexdigest(),
                latency_ms=latency_ms,
            )
        except Exception:
            pass


@router.post("/deep/stream")
async def chat_deep_stream(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Streaming deep analysis chat endpoint using Server-Sent Events."""
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    state = get_app_state()
    if not state.chat_service:
        raise HTTPException(status_code=503, detail="Chat service not initialized")

    async def generate_sse():
        start_time = time.time()
        audit = get_audit_logger()
        partial_response = ""

        try:
            memory_context = ""
            if request.session_id and state.memory and not request.skip_memory:
                try:
                    memory_context = await state.memory.retrieve_context(
                        request.query, request.session_id
                    )
                except Exception as exc:
                    print(f"[!] Memory retrieval failed: {exc}")

            try:
                result = await state.chat_service.generate(
                    endpoint="deep",
                    query=request.query,
                    context=request.context,
                    memory_context=memory_context,
                )
            except AllModelsFailed as exc:
                error_data = {
                    "type": "error",
                    "message": "All free-tier models exhausted for this endpoint",
                    "attempts": [
                        {
                            "model": attempt.model,
                            "error": attempt.error,
                            "timestamp": attempt.timestamp,
                        }
                        for attempt in exc.attempts
                    ],
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            model = result.get("model")
            yield f"data: {json.dumps({'type': 'start', 'query_type': 'deep', 'model': model})}\n\n"

            response_text = result.get("response", "")
            for idx in range(0, len(response_text), config.CHAT_STREAM_CHUNK_SIZE):
                chunk = response_text[idx : idx + config.CHAT_STREAM_CHUNK_SIZE]
                partial_response += chunk
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"

            latency_ms = (time.time() - start_time) * 1000
            done_data = {
                "type": "done",
                "response": response_text,
                "sources": result.get("sources", []),
                "next_actions": result.get("next_actions", []),
                "warnings": result.get("warnings", []),
                "latency_ms": latency_ms,
                "model": model,
            }
            yield f"data: {json.dumps(done_data)}\n\n"

            if request.session_id and state.memory:
                background_tasks.add_task(
                    state.memory.store_interaction,
                    request.session_id,
                    request.query,
                    response_text,
                )

        except Exception as exc:
            error_data = {
                "type": "error",
                "message": str(exc),
                "partial_response": partial_response,
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            try:
                latency_ms = (time.time() - start_time) * 1000
                audit.log_query(
                    user_id=user.user_id,
                    query_type="chat",
                    query_hash=hashlib.sha256(request.query.encode()).hexdigest(),
                    latency_ms=latency_ms,
                )
            except Exception:
                pass

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """Delete chat session memory."""
    state = get_app_state()
    if state.memory:
        background_tasks.add_task(state.memory.delete_session_memory, session_id)
        return {
            "status": "accepted",
            "message": f"Memory deletion scheduled for {session_id}",
        }

    return {"status": "ignored", "message": "Memory service not initialized"}


@router.get(
    "/session/{session_id}/message/{message_id}/graph",
    response_model=ChatGraphArtifactResponse,
    responses={
        404: {
            "model": ChatGraphArtifactNotFoundResponse,
            "description": "Graph artifact not found for this message",
        }
    },
)
async def get_message_graph(
    session_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
) -> Union[ChatGraphArtifactResponse, JSONResponse]:
    """
    Retrieve persisted graph data for a specific chat message.

    Returns the lineage graph that was generated with the original chat response.
    Use this endpoint to revisit answer-specific lineage after the conversation advances.
    """
    try:
        print(f"[DEBUG] Fetching artifact for session={session_id} message={message_id}")
        duckdb = get_duckdb_client()
        # Verify duckdb initialization state
        if not duckdb:
             raise RuntimeError("DuckDB client not initialized")
             
        artifact = await duckdb.get_chat_artifact(
            session_id=session_id,
            message_id=message_id,
            artifact_type="graph",
        )
    except RuntimeError as e:
        # DuckDB not initialized
        raise HTTPException(
            status_code=503,
            detail=f"Storage service error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_message_graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if artifact is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "Graph artifact not found",
                "session_id": session_id,
                "message_id": message_id,
                "suggestion": "Use the current lineage page for historical analysis",
            },
            headers={
                "Cache-Control": "no-cache",
            },
        )

    return ChatGraphArtifactResponse(
        session_id=session_id,
        message_id=message_id,
        nodes=artifact.get("nodes", []),
        edges=artifact.get("edges", []),
        metadata=artifact.get("metadata", {}),
    )
