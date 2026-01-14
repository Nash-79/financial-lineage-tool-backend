"""Utilities for managing and inspecting Qdrant indexes."""

from __future__ import annotations

from typing import Any, Dict, Optional


class IndexManager:
    """Lightweight wrapper to fetch index stats and HNSW config."""

    def __init__(self, qdrant_client: Any, collection_name: str):
        self.qdrant = qdrant_client
        self.collection = collection_name

    async def get_stats(self) -> Dict[str, Any]:
        """Return collection statistics and HNSW parameters."""
        if not self.qdrant:
            return {"collection": self.collection, "status": "unavailable"}

        try:
            info = await self.qdrant.collection_info(self.collection)
            result = info.get("result", {})
            config = result.get("config", {})
            hnsw_config: Optional[Dict[str, Any]] = (
                config.get("params", {}).get("hnsw_config") or {}
            )
            vectors_config = result.get("vectors_count", {})
            return {
                "collection": self.collection,
                "status": result.get("status", "unknown"),
                "vectors": result.get("vectors_count"),
                "hnsw": {
                    "ef_construct": hnsw_config.get("ef_construct"),
                    "m": hnsw_config.get("m"),
                },
                "shards_count": config.get("shard_number"),
            }
        except Exception as exc:
            return {
                "collection": self.collection,
                "status": "error",
                "error": str(exc),
            }
