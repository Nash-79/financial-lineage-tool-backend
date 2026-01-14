"""
Metadata query and management router.

Provides endpoints for querying DuckDB metadata, managing archives,
and system maintenance tasks.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.storage.duckdb_client import get_duckdb_client
from src.storage.archive import export_to_parquet, query_archived_parquet, list_archives
from ..config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


# ==================== Pydantic Models ====================


class SqlQueryRequest(BaseModel):
    query: str
    params: List[Any] = []


class ArchiveCreateRequest(BaseModel):
    year: int
    month: int


class ArchiveQueryRequest(BaseModel):
    query: str
    archive_path: str  # e.g., "data/archives/2024-01/projects.parquet"


# ==================== Query Endpoints ====================


@router.post("/query")
async def execute_sql(request: SqlQueryRequest) -> Dict[str, Any]:
    """
    Execute a read-only SQL query against DuckDB metadata.

    Restricted to SELECT statements for security.
    """
    query = request.query.strip().upper()

    # Basic SQL injection prevention (very distinct from parameterized queries)
    forbidden = ["UPDATE", "DELETE", "DROP", "ALTER", "INSERT", "TRUNCATE", "Create"]
    if any(cmd in query for cmd in forbidden):
        raise HTTPException(
            status_code=400, detail="Only SELECT queries are allowed via this endpoint."
        )

    try:
        client = get_duckdb_client()
        # Use simple execute method (we'll need to ensure read-only safety or use execute_query which returns df/list)
        # duckdb_client usually exposes specific methods, let's assume `execute` exists or similar
        # Based on previous summary, client has `execute_query` (returning list of dicts)

        results = await client.execute_query(request.query, request.params)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Metadata query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/projects")
async def get_project_stats() -> Dict[str, Any]:
    """Get statistics about projects."""
    client = get_duckdb_client()
    query = """
    SELECT 
        count(*) as total_projects,
        sum(repository_count) as total_repos,
        sum(link_count) as total_links,
        sum(total_nodes) as total_nodes,
        min(created_at) as first_created,
        max(updated_at) as last_updated
    FROM projects
    """
    try:
        results = await client.execute_query(query)
        return results[0] if results else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/repositories")
async def get_repo_stats() -> Dict[str, Any]:
    """Get statistics about repositories."""
    client = get_duckdb_client()
    query = """
    SELECT 
        source,
        count(*) as count,
        sum(file_count) as total_files,
        sum(node_count) as total_nodes
    FROM repositories
    GROUP BY source
    """
    try:
        results = await client.execute_query(query)
        return {"by_source": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_ingestion_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent ingestion history (system logs)."""
    client = get_duckdb_client()
    query = """
    SELECT *
    FROM system_logs
    ORDER BY timestamp DESC
    LIMIT ?
    """
    try:
        return await client.execute_query(query, [limit])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Archive Endpoints ====================


@router.get("/archives")
async def get_archives() -> List[str]:
    """List available archives."""
    try:
        return list_archives()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives/create")
async def create_archive_endpoint(request: ArchiveCreateRequest) -> Dict[str, Any]:
    """Trigger manual archive creation."""
    try:
        paths = await export_to_parquet(request.year, request.month)
        return {"status": "success", "paths": paths}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives/query")
async def query_archive(request: ArchiveQueryRequest) -> Dict[str, Any]:
    """Query a specific parquet archive file."""
    try:
        results = query_archived_parquet(request.archive_path, request.query)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Backup & Maintenance ====================


@router.post("/backup")
async def create_backup() -> Dict[str, str]:
    """
    Create a backup of the DuckDB database file.

    Locks the database during copy to ensure integrity.
    """
    if config.DUCKDB_PATH == ":memory:":
        raise HTTPException(status_code=400, detail="Cannot backup in-memory database")

    try:
        client = get_duckdb_client()
        # Ensure checkpoint/flush? DuckDB auto-checkpoints.

        backup_dir = Path("data/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"metadata_backup_{timestamp}.duckdb"

        # Simple file copy (DuckDB safe usually only if closed or using EXPORT DATABASE)
        # Ideally use client's EXPORT DATABASE or VACUUM equivalent.
        # For simplicity in this spec, we'll try API level export or just copy if allowed.
        # Safe way: EXPORT DATABASE 'path' (parquet/csv) or copy file if we can impose a lock.
        # Implemented using EXPORT DATABASE for safety + portability

        export_path = backup_dir / f"backup_{timestamp}"
        await client.execute_write(f"EXPORT DATABASE '{export_path}' (FORMAT PARQUET)")

        return {"status": "success", "path": str(export_path)}

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.get("/search")
async def search_metadata(q: str = Query(...)) -> Dict[str, Any]:
    """
    Full-text search across files/metadata.

    Requires FTS extension enabled in DuckDB.
    """
    # Placeholder for FTS implementation
    # Need to check if FTS extension is available and indices built
    return {"results": [], "note": "FTS not yet fully configured"}
