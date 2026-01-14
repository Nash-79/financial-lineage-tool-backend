"""
Ingestion log retrieval router.

Provides endpoints for downloading or viewing ingestion JSONL logs.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from src.services.ingestion_tracker import get_tracker
from ..config import config
from ..middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/ingestion",
    tags=["ingestion"],
    dependencies=[Depends(get_current_user)],
)


class IngestionLogEntry(BaseModel):
    """Ingestion log index entry."""

    ingestion_id: str
    source: str
    project_id: str
    project_status: str
    repository_id: str
    run_id: Optional[str]
    status: str
    started_at: str
    completed_at: Optional[str]
    filenames: List[str]
    source_repo: Optional[str]


class IngestionLogsResponse(BaseModel):
    """Response model for ingestion logs list endpoint."""

    sessions: List[IngestionLogEntry]
    total: int
    limit: int


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _load_index_entries(base_dir: Path) -> List[Dict[str, Any]]:
    """Scan for ingestion_index.json files and load them."""
    entries: List[Dict[str, Any]] = []

    if not base_dir.exists():
        return entries

    # Search for all ingestion_index.json files
    for index_path in base_dir.rglob("ingestion_index.json"):
        try:
            with index_path.open("r", encoding="utf-8") as handle:
                entry = json.load(handle)
                entries.append(entry)
        except (json.JSONDecodeError, IOError) as e:
            # Skip malformed or unreadable index files
            continue

    return entries


@router.get("/logs", response_model=IngestionLogsResponse)
async def list_ingestion_logs(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    source: Optional[str] = Query(None, description="Filter by source (upload/github)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
) -> IngestionLogsResponse:
    """
    List ingestion log sessions ordered by most recent.

    Scans the storage directory for ingestion_index.json files and returns
    a filtered, sorted list of ingestion sessions.
    """
    base_dir = Path(config.STORAGE_PATH)

    # Load all index entries
    entries = _load_index_entries(base_dir)

    # Apply filters
    if project_id:
        entries = [e for e in entries if e.get("project_id") == project_id]

    if source:
        entries = [e for e in entries if e.get("source") == source]

    if status:
        entries = [e for e in entries if e.get("status") == status]

    # Sort by started_at descending (most recent first)
    entries.sort(key=lambda e: e.get("started_at", ""), reverse=True)

    total = len(entries)
    entries = entries[:limit]

    return IngestionLogsResponse(
        sessions=[IngestionLogEntry(**e) for e in entries],
        total=total,
        limit=limit,
    )


@router.get("/logs/{ingestion_id}")
async def get_ingestion_logs(
    ingestion_id: str,
    format: Literal["json", "jsonl"] = Query("json", description="Response format"),
    download: bool = Query(False, description="Return as attachment if true"),
) -> Response:
    """Retrieve ingestion logs for a given ingestion_id."""
    tracker = get_tracker()
    base_dir = Path(config.STORAGE_PATH)
    log_path = tracker.find_log_path(ingestion_id, base_dir)

    if not log_path or not log_path.exists():
        raise HTTPException(status_code=404, detail="Ingestion log not found")

    headers = {}
    if download:
        ext = "jsonl" if format == "jsonl" else "json"
        headers["Content-Disposition"] = (
            f'attachment; filename="ingestion_{ingestion_id}.{ext}"'
        )

    if format == "jsonl":
        content = log_path.read_text(encoding="utf-8")
        return Response(
            content=content, media_type="application/x-ndjson", headers=headers
        )

    events = _load_jsonl(log_path)
    payload = {
        "ingestion_id": ingestion_id,
        "events": events,
    }
    content = json.dumps(payload, indent=2, ensure_ascii=True)
    return Response(content=content, media_type="application/json", headers=headers)
