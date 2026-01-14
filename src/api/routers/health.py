"""Health and monitoring endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Query

from ..config import config
from src.utils import metrics
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

    rag_mode = "legacy"
    if state.chat_service:
        rag_mode = "hybrid"
    elif config.USE_LLAMAINDEX and state.llamaindex_service:
        rag_mode = "llamaindex"

    # Check LlamaIndex only if it's the active RAG engine
    if rag_mode == "llamaindex" and state.llamaindex_service:
        try:
            llamaindex_health = await state.llamaindex_service.health_check()
            services["llamaindex"] = (
                "up" if llamaindex_health.get("llamaindex") == "healthy" else "down"
            )
        except Exception:
            services["llamaindex"] = "down"

    # Add mode information
    services["rag_mode"] = rag_mode
    services["openrouter"] = "configured" if config.OPENROUTER_API_KEY else "missing"

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

    required_services = ["api", "ollama", "qdrant", "neo4j"]
    if rag_mode == "llamaindex":
        required_services.append("llamaindex")

    overall = (
        "healthy"
        if all(services.get(name) == "up" for name in required_services)
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
        if state.chat_service:
            summary = metrics.get_registry().get_summary()

            def filter_metrics(group: str) -> Dict[str, Any]:
                return {
                    key: value
                    for key, value in summary.get(group, {}).items()
                    if key.startswith("chat_")
                }

            def aggregate_histogram(prefix: str) -> Dict[str, float]:
                count = 0
                total = 0.0
                for key, value in summary.get("histograms", {}).items():
                    if key.startswith(prefix):
                        count += int(value.get("count", 0))
                        total += float(value.get("sum", 0.0))
                avg = (total / count) if count else 0.0
                return {"count": count, "sum": total, "avg": avg}

            total_queries = int(
                sum(
                    value
                    for key, value in summary.get("counters", {}).items()
                    if key.startswith("chat_request_count")
                )
            )
            latency = aggregate_histogram("chat_latency_seconds")

            return RAGStatusResponse(
                mode="hybrid",
                total_queries=total_queries,
                cache_hit_rate=0.0,
                avg_latency_ms=latency["avg"] * 1000.0 if latency["count"] else 0.0,
                status="healthy",
                chat_metrics={
                    "counters": filter_metrics("counters"),
                    "gauges": filter_metrics("gauges"),
                    "histograms": filter_metrics("histograms"),
                },
            )
        if config.USE_LLAMAINDEX and state.llamaindex_service:
            llamaindex_metrics = state.llamaindex_service.get_metrics()
            return RAGStatusResponse(
                mode=llamaindex_metrics.get("mode", "llamaindex"),
                total_queries=llamaindex_metrics.get("total_queries", 0),
                cache_hit_rate=llamaindex_metrics.get("query_cache_hit_rate", 0.0),
                avg_latency_ms=llamaindex_metrics.get("avg_query_latency_ms", 0.0),
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
