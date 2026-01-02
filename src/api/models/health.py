"""Health and status models."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str
    services: Dict[str, Any]
    timestamp: str


class RAGStatusResponse(BaseModel):
    """Response model for RAG status endpoint."""

    mode: str  # "llamaindex" or "legacy"
    total_queries: int
    cache_hit_rate: float
    avg_latency_ms: float
    status: str
