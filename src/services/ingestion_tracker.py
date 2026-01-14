"""
Ingestion tracking service for real-time progress updates.

Provides a centralized way to track file ingestion progress
and broadcast updates via WebSocket to connected clients.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class IngestionStatus(str, Enum):
    """Ingestion status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class FileStatus(str, Enum):
    """Individual file processing status."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    COMPLETE = "complete"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class FileProgress:
    """Progress state for a single file."""

    path: str
    status: FileStatus = FileStatus.PENDING
    nodes_created: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class IngestionSession:
    """Tracks progress for an ingestion session."""

    ingestion_id: str
    source: str  # "github" or "upload"
    project_id: str
    repository_id: str
    total_files: int
    log_path: Optional[str] = None
    verbose: bool = False
    status: IngestionStatus = IngestionStatus.PENDING
    files_processed: int = 0
    files_failed: int = 0
    total_nodes_created: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    file_progress: Dict[str, FileProgress] = field(default_factory=dict)
    errors: List[Dict[str, str]] = field(default_factory=list)
    run_id: Optional[str] = None
    project_status: str = "active"
    source_repo: Optional[str] = None
    filenames: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for API response."""
        return {
            "ingestion_id": self.ingestion_id,
            "source": self.source,
            "project_id": self.project_id,
            "repository_id": self.repository_id,
            "status": self.status.value,
            "total_files": self.total_files,
            "files_processed": self.files_processed,
            "files_failed": self.files_failed,
            "total_nodes_created": self.total_nodes_created,
            "percentage": (
                round((self.files_processed / self.total_files) * 100)
                if self.total_files > 0
                else 0
            ),
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": (
                (self.completed_at or datetime.utcnow()) - self.started_at
            ).total_seconds(),
            "errors": self.errors,
            "run_id": self.run_id,
            "project_status": self.project_status,
            "source_repo": self.source_repo,
            "filenames": self.filenames,
        }

    def to_index_entry(self) -> Dict[str, Any]:
        """Convert session to index entry for lightweight listing."""
        return {
            "ingestion_id": self.ingestion_id,
            "source": self.source,
            "project_id": self.project_id,
            "project_status": self.project_status,
            "repository_id": self.repository_id,
            "run_id": self.run_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "filenames": self.filenames,
            "source_repo": self.source_repo,
        }


class IngestionTracker:
    """
    Manages ingestion sessions and broadcasts progress via WebSocket.

    Usage:
        tracker = IngestionTracker(broadcast_fn=websocket_manager.broadcast)
        session = await tracker.start_session(
            source="github",
            project_id="...",
            repository_id="...",
            file_paths=["a.sql", "b.sql"]
        )

        for file_path in file_paths:
            await tracker.update_file_status(session.ingestion_id, file_path, FileStatus.DOWNLOADING)
            # ... download file ...
            await tracker.update_file_status(session.ingestion_id, file_path, FileStatus.PARSING)
            # ... parse file ...
            await tracker.file_complete(session.ingestion_id, file_path, nodes_created=5)

        await tracker.complete_session(session.ingestion_id)
    """

    def __init__(self, broadcast_fn: Optional[Callable] = None):
        """
        Initialize the tracker.

        Args:
            broadcast_fn: Async function to broadcast messages to WebSocket clients.
                         Should accept a Dict[str, Any] message.
        """
        self._sessions: Dict[str, IngestionSession] = {}
        self._broadcast_fn = broadcast_fn
        self._lock = asyncio.Lock()

    def set_broadcast_fn(self, broadcast_fn: Callable):
        """Set or update the broadcast function."""
        self._broadcast_fn = broadcast_fn

    async def _broadcast(self, message_type: str, data: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        if self._broadcast_fn:
            message = {
                "type": message_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            }
            try:
                await self._broadcast_fn(message)
            except Exception as e:
                logger.warning(f"Failed to broadcast {message_type}: {e}")

    async def start_session(
        self,
        source: str,
        project_id: str,
        repository_id: str,
        file_paths: List[str],
        log_dir: Optional[Path] = None,
        verbose: bool = False,
        run_id: Optional[str] = None,
        project_status: str = "active",
        source_repo: Optional[str] = None,
    ) -> IngestionSession:
        """
        Start a new ingestion session.

        Args:
            source: "github" or "upload"
            project_id: Target project ID
            repository_id: Target repository ID
            file_paths: List of file paths to process
            log_dir: Optional directory for log files
            verbose: Enable verbose logging
            run_id: Optional run identifier
            project_status: Project status (active/inactive)
            source_repo: Optional source repository (e.g., "owner/repo")

        Returns:
            New IngestionSession instance
        """
        ingestion_id = str(uuid.uuid4())

        # Extract filenames from paths
        filenames = [Path(p).name for p in file_paths]

        session = IngestionSession(
            ingestion_id=ingestion_id,
            source=source,
            project_id=project_id,
            repository_id=repository_id,
            total_files=len(file_paths),
            status=IngestionStatus.IN_PROGRESS,
            verbose=verbose,
            run_id=run_id,
            project_status=project_status,
            source_repo=source_repo,
            filenames=filenames,
        )

        # Initialize file progress
        for path in file_paths:
            session.file_progress[path] = FileProgress(path=path)

        async with self._lock:
            self._sessions[ingestion_id] = session

        if log_dir:
            log_path = Path(log_dir) / f"ingestion_{ingestion_id}.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            session.log_path = str(log_path)

            # Create ingestion index file
            await self._write_index(log_dir, session)

        # Broadcast start
        start_payload = {
            "ingestion_id": ingestion_id,
            "source": source,
            "project_id": project_id,
            "repository_id": repository_id,
            "total_files": len(file_paths),
        }
        await self._broadcast("ingestion_started", start_payload)
        await self.log_event(ingestion_id, "ingestion_started", start_payload)

        logger.info(
            f"Started ingestion session {ingestion_id} with {len(file_paths)} files"
        )
        return session

    async def update_file_status(
        self,
        ingestion_id: str,
        file_path: str,
        status: FileStatus,
        error: Optional[str] = None,
    ):
        """
        Update the status of a file being processed.

        Args:
            ingestion_id: Session ID
            file_path: Path of the file
            status: New status
            error: Error message if status is ERROR
        """
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                logger.warning(f"Session {ingestion_id} not found")
                return

            file_progress = session.file_progress.get(file_path)
            if not file_progress:
                file_progress = FileProgress(path=file_path)
                session.file_progress[file_path] = file_progress

            file_progress.status = status
            if status == FileStatus.DOWNLOADING:
                file_progress.started_at = datetime.utcnow()
            if error:
                file_progress.error = error

        progress_payload = {
            "ingestion_id": ingestion_id,
            "current_file": file_path,
            "status": status.value,
            "files_processed": session.files_processed,
            "total_files": session.total_files,
            "percentage": (
                round((session.files_processed / session.total_files) * 100)
                if session.total_files > 0
                else 0
            ),
            "nodes_created": session.total_nodes_created,
            "error": error,
        }
        # Broadcast progress
        await self._broadcast("ingestion_progress", progress_payload)
        await self.log_event(ingestion_id, "ingestion_progress", progress_payload)

    async def file_complete(
        self,
        ingestion_id: str,
        file_path: str,
        nodes_created: int = 0,
    ):
        """
        Mark a file as successfully processed.

        Args:
            ingestion_id: Session ID
            file_path: Path of the file
            nodes_created: Number of lineage nodes created
        """
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                return

            file_progress = session.file_progress.get(file_path)
            if file_progress:
                file_progress.status = FileStatus.COMPLETE
                file_progress.nodes_created = nodes_created
                file_progress.completed_at = datetime.utcnow()

            session.files_processed += 1
            session.total_nodes_created += nodes_created

        progress_payload = {
            "ingestion_id": ingestion_id,
            "current_file": file_path,
            "status": FileStatus.COMPLETE.value,
            "files_processed": session.files_processed,
            "total_files": session.total_files,
            "percentage": (
                round((session.files_processed / session.total_files) * 100)
                if session.total_files > 0
                else 0
            ),
            "nodes_created": session.total_nodes_created,
            "error": None,
        }
        await self._broadcast("ingestion_progress", progress_payload)
        await self.log_event(ingestion_id, "ingestion_progress", progress_payload)

    async def file_error(
        self,
        ingestion_id: str,
        file_path: str,
        error: str,
    ):
        """
        Mark a file as failed.

        Args:
            ingestion_id: Session ID
            file_path: Path of the file
            error: Error message
        """
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                return

            file_progress = session.file_progress.get(file_path)
            if file_progress:
                file_progress.status = FileStatus.ERROR
                file_progress.error = error
                file_progress.completed_at = datetime.utcnow()

            session.files_processed += 1
            session.files_failed += 1
            session.errors.append({"file": file_path, "error": error})

        progress_payload = {
            "ingestion_id": ingestion_id,
            "current_file": file_path,
            "status": FileStatus.ERROR.value,
            "files_processed": session.files_processed,
            "total_files": session.total_files,
            "percentage": (
                round((session.files_processed / session.total_files) * 100)
                if session.total_files > 0
                else 0
            ),
            "nodes_created": session.total_nodes_created,
            "error": error,
        }
        await self._broadcast("ingestion_progress", progress_payload)
        await self.log_event(ingestion_id, "ingestion_progress", progress_payload)

    async def file_skipped(
        self,
        ingestion_id: str,
        file_path: str,
        reason: str = "unsupported_file_type",
    ):
        """
        Mark a file as skipped.

        Args:
            ingestion_id: Session ID
            file_path: Path of the file
            reason: Reason for skipping
        """
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                return

            file_progress = session.file_progress.get(file_path)
            if file_progress:
                file_progress.status = FileStatus.SKIPPED
                file_progress.error = reason

            session.files_processed += 1

        await self.log_event(
            ingestion_id,
            "file_skipped",
            {
                "file": file_path,
                "reason": reason,
                "files_processed": session.files_processed,
                "total_files": session.total_files,
            },
        )

    async def complete_session(self, ingestion_id: str) -> Optional[IngestionSession]:
        """
        Mark an ingestion session as complete.

        Args:
            ingestion_id: Session ID

        Returns:
            Completed session or None if not found
        """
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                return None

            session.completed_at = datetime.utcnow()
            if session.files_failed > 0:
                session.status = IngestionStatus.COMPLETED_WITH_ERRORS
            else:
                session.status = IngestionStatus.COMPLETED

        duration = (session.completed_at - session.started_at).total_seconds()

        completion_payload = {
            "ingestion_id": ingestion_id,
            "status": session.status.value,
            "files_processed": session.files_processed,
            "files_failed": session.files_failed,
            "total_nodes_created": session.total_nodes_created,
            "duration_seconds": duration,
            "errors": session.errors,
        }
        await self._broadcast("ingestion_complete", completion_payload)
        await self.log_event(ingestion_id, "ingestion_complete", completion_payload)

        # Update ingestion index with completion data
        if session.log_path:
            log_dir = Path(session.log_path).parent
            await self._write_index(log_dir, session)

        logger.info(
            f"Completed ingestion session {ingestion_id}: "
            f"{session.files_processed} files, {session.files_failed} failed, "
            f"{session.total_nodes_created} nodes in {duration:.1f}s"
        )

        return session

    async def fail_session(
        self, ingestion_id: str, error: str
    ) -> Optional[IngestionSession]:
        """
        Mark an ingestion session as failed.

        Args:
            ingestion_id: Session ID
            error: Error message

        Returns:
            Failed session or None if not found
        """
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                return None

            session.completed_at = datetime.utcnow()
            session.status = IngestionStatus.FAILED
            session.errors.append({"file": "_session", "error": error})

        completion_payload = {
            "ingestion_id": ingestion_id,
            "status": IngestionStatus.FAILED.value,
            "files_processed": session.files_processed,
            "files_failed": session.files_failed,
            "total_nodes_created": session.total_nodes_created,
            "duration_seconds": (
                session.completed_at - session.started_at
            ).total_seconds(),
            "errors": session.errors,
        }
        await self._broadcast("ingestion_complete", completion_payload)
        await self.log_event(ingestion_id, "ingestion_complete", completion_payload)

        # Update ingestion index with failure data
        if session.log_path:
            log_dir = Path(session.log_path).parent
            await self._write_index(log_dir, session)

        logger.error(f"Failed ingestion session {ingestion_id}: {error}")
        return session

    def get_session(self, ingestion_id: str) -> Optional[IngestionSession]:
        """Get a session by ID."""
        return self._sessions.get(ingestion_id)

    def get_active_sessions(self) -> List[IngestionSession]:
        """Get all active (in-progress) sessions."""
        return [
            s
            for s in self._sessions.values()
            if s.status == IngestionStatus.IN_PROGRESS
        ]

    def get_history(
        self,
        project_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get ingestion history.

        Args:
            project_id: Filter by project (optional)
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries
        """
        sessions = list(self._sessions.values())

        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]

        # Sort by start time, newest first
        sessions.sort(key=lambda s: s.started_at, reverse=True)

        return [s.to_dict() for s in sessions[:limit]]

    async def log_event(
        self,
        ingestion_id: str,
        event_type: str,
        payload: Dict[str, Any],
        level: str = "info",
    ) -> None:
        """Append a structured event to the ingestion log when enabled."""
        async with self._lock:
            session = self._sessions.get(ingestion_id)
            if not session:
                return
            if level == "debug" and not session.verbose:
                return
            log_path = session.log_path

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "ingestion_id": ingestion_id,
            "type": event_type,
            "level": level,
            "payload": payload,
        }
        if log_path:
            await self._append_log(log_path, event)
        self._emit_otel_log(event, level)

    def _emit_otel_log(self, event: Dict[str, Any], level: str) -> None:
        """Emit ingestion events through standard logging for OTEL capture."""
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warn": logging.WARNING,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }
        log_level = level_map.get(level, logging.INFO)
        try:
            logger.log(
                log_level,
                "ingestion_event",
                extra={
                    "ingestion_id": event.get("ingestion_id"),
                    "ingestion_event_type": event.get("type"),
                    "ingestion_event_level": event.get("level"),
                    "ingestion_event_payload": event.get("payload"),
                },
            )
        except Exception:
            logger.log(
                log_level, "ingestion_event=%s", json.dumps(event, ensure_ascii=True)
            )

    async def log_debug(
        self,
        ingestion_id: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a debug event to the ingestion log when verbose is enabled."""
        await self.log_event(
            ingestion_id,
            "debug",
            {
                "message": message,
                "context": payload or {},
            },
            level="debug",
        )

    async def log_stage(
        self,
        ingestion_id: str,
        stage: str,
        status: str,
        file_path: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Log a pipeline stage event.

        Args:
            ingestion_id: Session ID
            stage: Stage name (parsing, chunking, embedding, indexing, llm)
            status: Stage status (started, completed, failed, skipped)
            file_path: Optional file being processed
            summary: Optional summary metrics (e.g., chunks_created, nodes_created)
            error: Optional error message if failed
        """
        payload = {
            "stage": stage,
            "status": status,
        }
        if file_path:
            payload["file"] = file_path
        if summary:
            payload["summary"] = summary
        if error:
            payload["error"] = error

        await self.log_event(
            ingestion_id,
            "stage_event",
            payload,
            level="info",
        )

    def find_log_path(self, ingestion_id: str, base_dir: Path) -> Optional[Path]:
        """Locate the ingestion log for a session by ingestion_id."""
        session = self._sessions.get(ingestion_id)
        if session and session.log_path:
            log_path = Path(session.log_path)
            if log_path.exists():
                return log_path

        pattern = f"ingestion_{ingestion_id}.jsonl"
        matches = list(base_dir.rglob(pattern)) if base_dir.exists() else []
        if not matches:
            return None
        matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return matches[0]

    async def _append_log(self, log_path: str, event: Dict[str, Any]) -> None:
        """Write a log event to the session JSONL file."""
        payload = json.dumps(event, ensure_ascii=True)
        path = Path(log_path)

        def _write_line() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")

        await asyncio.to_thread(_write_line)

    async def _write_index(self, log_dir: Path, session: IngestionSession) -> None:
        """Write or update the ingestion index file for this run."""
        index_path = Path(log_dir) / "ingestion_index.json"
        index_entry = session.to_index_entry()

        def _write_file() -> None:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with index_path.open("w", encoding="utf-8") as handle:
                json.dump(index_entry, handle, indent=2, ensure_ascii=False)

        await asyncio.to_thread(_write_file)
        logger.debug(f"Updated ingestion index at {index_path}")


# Global tracker instance
_tracker: Optional[IngestionTracker] = None


def get_tracker() -> IngestionTracker:
    """Get the global ingestion tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = IngestionTracker()
    return _tracker


def set_tracker_broadcast(broadcast_fn: Callable):
    """Set the broadcast function for the global tracker."""
    get_tracker().set_broadcast_fn(broadcast_fn)
