"""Health and monitoring endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Query

from ..config import config
from ..models.health import HealthResponse, RAGStatusResponse

if TYPE_CHECKING:
    pass

router = APIRouter(tags=["health"])


def get_app_state() -> Any:
    """Get application state from FastAPI app.

    This is a placeholder that will be replaced with actual state injection.
    The state will be passed via dependency injection in main.py.
    """
    # This will be replaced with proper dependency injection
    from ..main_local import state

    return state


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check health of all local services.

    Checks connectivity and status of:
    - Ollama (LLM service)
    - Qdrant (vector database)
    - Neo4j (graph database)
    - LlamaIndex (if enabled)

    Returns:
        HealthResponse with overall status and individual service statuses.
    """
    state = get_app_state()

    services: Dict[str, str] = {
        "api": "up",
        "ollama": "unknown",
        "qdrant": "unknown",
        "neo4j": "unknown",
    }

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            services["ollama"] = "up" if r.status_code == 200 else "down"
    except Exception:
        services["ollama"] = "down"

    # Check Qdrant
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"http://{config.QDRANT_HOST}:{config.QDRANT_PORT}/")
            services["qdrant"] = "up" if r.status_code == 200 else "down"
    except Exception:
        services["qdrant"] = "down"

    # Check Neo4j
    try:
        if state.graph:
            # Try a simple query to verify connection
            state.graph.get_stats()
            services["neo4j"] = "up"
        else:
            services["neo4j"] = "down"
    except Exception:
        services["neo4j"] = "down"

    # Check LlamaIndex if enabled
    if config.USE_LLAMAINDEX and state.llamaindex_service:
        try:
            llamaindex_health = await state.llamaindex_service.health_check()
            services["llamaindex"] = llamaindex_health["llamaindex"]
        except Exception:
            services["llamaindex"] = "degraded"

    # Add mode information
    services["rag_mode"] = "llamaindex" if config.USE_LLAMAINDEX else "legacy"

    # Add database migration status
    database_status: Dict[str, Any] = {}
    try:
        from ...storage.duckdb_client import get_duckdb_client

        db = get_duckdb_client()
        migration_status = db.get_migration_status()
        database_status = {
            "schema_version": migration_status["current_version"],
            "is_current": migration_status["is_current"],
            "total_migrations": migration_status["total_migrations"],
            "last_migration": (
                migration_status["migrations"][-1]["applied_at"]
                if migration_status["migrations"]
                else None
            ),
        }
    except Exception as e:
        # Log error but don't fail health check
        database_status = {"error": str(e)}

    overall = (
        "healthy"
        if all(
            s == "up"
            for k, s in services.items()
            if k not in ["rag_mode", "llamaindex"]
            or k == "llamaindex"
            and config.USE_LLAMAINDEX
        )
        else "degraded"
    )

    return HealthResponse(
        status=overall,
        services=services,
        database=database_status,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/api/v1/rag/status", response_model=RAGStatusResponse)
async def get_rag_status() -> RAGStatusResponse:
    """Get RAG pipeline status and metrics.

    Returns:
        RAGStatusResponse with current mode, query count, cache hit rate,
        and average latency.

    Raises:
        HTTPException: If unable to retrieve RAG status.
    """
    state = get_app_state()

    try:
        if config.USE_LLAMAINDEX and state.llamaindex_service:
            metrics = state.llamaindex_service.get_metrics()
            return RAGStatusResponse(
                mode=metrics.get("mode", "llamaindex"),
                total_queries=metrics.get("total_queries", 0),
                cache_hit_rate=metrics.get("query_cache_hit_rate", 0.0),
                avg_latency_ms=metrics.get("avg_query_latency_ms", 0.0),
                status="healthy",
            )
        else:
            return RAGStatusResponse(
                mode="legacy",
                total_queries=0,
                cache_hit_rate=0.0,
                avg_latency_ms=0.0,
                status="healthy",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RAG status: {e}")


@router.get("/api/v1/metrics/activity")
async def get_activity_metrics() -> Dict[str, Any]:
    """Get activity tracking metrics for monitoring system usage.

    Returns aggregated metrics including:
    - Total requests and success rate
    - Query/ingestion counts
    - Average latency
    - Cache hit rates
    - Top endpoints
    - Error types

    Returns:
        Dictionary containing activity metrics.

    Raises:
        HTTPException: If activity tracker is not initialized.
    """
    state = get_app_state()

    if not state.activity_tracker:
        raise HTTPException(status_code=503, detail="Activity tracker not initialized")

    return state.activity_tracker.get_metrics()


@router.get("/api/v1/metrics/events")
async def get_recent_events(limit: int = Query(default=100, le=1000)) -> Dict[str, Any]:
    """Get recent activity events for detailed analysis.

    Args:
        limit: Maximum number of events to return (max 1000).

    Returns:
        Dictionary with events list and total event count.

    Raises:
        HTTPException: If activity tracker is not initialized.
    """
    state = get_app_state()

    if not state.activity_tracker:
        raise HTTPException(status_code=503, detail="Activity tracker not initialized")

    return {
        "events": state.activity_tracker.get_recent_events(limit=limit),
        "total_events": len(state.activity_tracker.events),
    }
