"""Configuration endpoints for SQL dialects and system settings."""

import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.llm.free_tier import FREE_TIER_MODELS
from ..config import config
from ..models.config import SQLDialect

router = APIRouter(prefix="/api/v1/config", tags=["config"])

_CONFIG_CACHE: Dict[str, Any] = {"timestamp": 0.0, "payload": None}
_CONFIG_TTL_SECONDS = 60


@router.get("", response_model=Dict[str, Any])
async def get_config_root() -> Dict[str, Any]:
    """Return core configuration for frontend clients."""
    now = time.time()
    cached_payload = _CONFIG_CACHE.get("payload")
    if cached_payload and now - _CONFIG_CACHE["timestamp"] < _CONFIG_TTL_SECONDS:
        return cached_payload

    payload = {
        "chat_endpoint_models": config.get_chat_endpoint_models(),
        "free_tier_models": sorted(FREE_TIER_MODELS),
    }
    _CONFIG_CACHE["timestamp"] = now
    _CONFIG_CACHE["payload"] = payload
    return payload


@router.get("/sql-dialects", response_model=List[SQLDialect])
async def get_sql_dialects() -> List[SQLDialect]:
    """Get available SQL dialects for SQL ingestion.

    Returns list of supported SQL dialects with their configurations.
    Frontend uses this to populate dialect selector during ingestion.

    Returns:
        List of SQL dialect configurations.
    """
    try:
        from ...config.sql_dialects import get_enabled_dialects

        enabled = get_enabled_dialects()
        return [
            SQLDialect(
                id=dialect["id"],
                display_name=dialect["display_name"],
                sqlglot_key=dialect["sqlglot_read_key"],
                is_default=bool(dialect.get("is_default")),
                enabled=bool(dialect.get("enabled", True)),
            )
            for dialect in enabled
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch SQL dialects: {e}"
        )
