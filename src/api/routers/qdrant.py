"""Qdrant chunk lookup endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..config import config

router = APIRouter(prefix="/api/v1/qdrant", tags=["qdrant"])


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


@router.get("/chunks/{point_id}")
async def get_chunk(point_id: str) -> Dict[str, Any]:
    """Resolve a Qdrant chunk by point ID."""
    state = get_app_state()
    if not state.qdrant:
        raise HTTPException(status_code=503, detail="Qdrant not initialized")

    point = await state.qdrant.get_point(config.QDRANT_COLLECTION, point_id)
    if not point:
        raise HTTPException(status_code=404, detail="Chunk not found")

    payload = point.get("payload", {}) or {}
    content = payload.get("content") or payload.get("text") or ""

    return {
        "id": point.get("id"),
        "collection": config.QDRANT_COLLECTION,
        "payload": payload,
        "content_excerpt": content[:200],
    }
