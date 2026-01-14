"""
Snapshot management API endpoints.

Provides REST API access to DuckDB snapshot metadata and management.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.storage.duckdb_client import get_duckdb_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])


class SnapshotMetadata(BaseModel):
    """Snapshot metadata response model."""

    id: str
    timestamp: str
    file_size_bytes: int
    record_count: int
    file_path: str


@router.get("", response_model=List[SnapshotMetadata])
async def list_snapshots():
    """
    List all available DuckDB snapshots.

    Returns snapshots sorted by timestamp (descending - newest first).
    Only available when DuckDB is running in memory mode with snapshots enabled.

    Returns:
        List of snapshot metadata

    Raises:
        HTTPException: If snapshots are not enabled or an error occurs
    """
    try:
        duckdb_client = get_duckdb_client()

        if not duckdb_client.snapshot_manager:
            raise HTTPException(
                status_code=400,
                detail="Snapshots not enabled (running in persistent mode)",
            )

        snapshots = duckdb_client.snapshot_manager.list_snapshots()
        return snapshots

    except Exception as e:
        logger.error(f"Error listing snapshots: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list snapshots: {str(e)}"
        )


@router.get("/{snapshot_id}", response_model=SnapshotMetadata)
async def get_snapshot(snapshot_id: str):
    """
    Get metadata for a specific snapshot.

    Args:
        snapshot_id: Snapshot ID (format: YYYYMMDD_HHMMSS)

    Returns:
        Snapshot metadata

    Raises:
        HTTPException: If snapshot not found or an error occurs
    """
    try:
        duckdb_client = get_duckdb_client()

        if not duckdb_client.snapshot_manager:
            raise HTTPException(
                status_code=400,
                detail="Snapshots not enabled (running in persistent mode)",
            )

        snapshots = duckdb_client.snapshot_manager.list_snapshots()

        # Find snapshot by ID
        snapshot = next((s for s in snapshots if s["id"] == snapshot_id), None)

        if not snapshot:
            raise HTTPException(
                status_code=404, detail=f"Snapshot not found: {snapshot_id}"
            )

        return snapshot

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting snapshot {snapshot_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get snapshot: {str(e)}")
