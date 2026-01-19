"""
Unified log reader for all log categories.

Provides a single interface to query logs from:
- app: Application logs (Loguru JSONL)
- chat: Chat interaction logs (JSONL)
- audit: Audit/compliance logs (JSONL)
- ingestion: Ingestion session logs (JSONL)
"""

from __future__ import annotations

import gzip
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

from loguru import logger


class LogCategory(str, Enum):
    """Log categories."""

    APP = "app"
    CHAT = "chat"
    AUDIT = "audit"
    INGESTION = "ingestion"


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


LEVEL_PRIORITY = {
    LogLevel.DEBUG: 0,
    LogLevel.INFO: 1,
    LogLevel.WARNING: 2,
    LogLevel.ERROR: 3,
    LogLevel.CRITICAL: 4,
}


@dataclass
class LogFilter:
    """Filter criteria for log queries."""

    categories: list[LogCategory] = field(default_factory=lambda: list(LogCategory))
    level: Optional[LogLevel] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    module: Optional[str] = None
    request_id: Optional[str] = None
    ingestion_id: Optional[str] = None
    chat_id: Optional[str] = None
    search: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass
class LogEntry:
    """Unified log entry."""

    timestamp: datetime
    category: LogCategory
    level: str
    message: str
    module: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    extra: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "level": self.level,
            "message": self.message,
            "module": self.module,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "extra": self.extra,
        }


@dataclass
class CategoryStats:
    """Statistics for a log category."""

    category: LogCategory
    total_count: int
    error_count: int
    oldest: Optional[datetime]
    newest: Optional[datetime]
    storage_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "category": self.category.value,
            "total_count": self.total_count,
            "error_count": self.error_count,
            "oldest": self.oldest.isoformat() if self.oldest else None,
            "newest": self.newest.isoformat() if self.newest else None,
            "storage_bytes": self.storage_bytes,
        }


@dataclass
class LogQueryResult:
    """Result of a log query."""

    entries: list[LogEntry]
    total_count: int
    limit: int
    offset: int
    has_more: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "total_count": self.total_count,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
        }


class UnifiedLogReader:
    """Unified reader for all log categories."""

    def __init__(self, log_path: Optional[str] = None):
        """Initialize log reader.

        Args:
            log_path: Base path for logs. Defaults to LOG_PATH env var or ./logs.
        """
        self.log_path = Path(log_path or os.getenv("LOG_PATH", "./logs"))

    def _get_category_path(self, category: LogCategory) -> Path:
        """Get the path for a log category."""
        return self.log_path / category.value

    def _list_log_files(
        self, category: LogCategory, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> list[Path]:
        """List log files for a category within date range."""
        cat_path = self._get_category_path(category)
        if not cat_path.exists():
            return []

        files = []
        for f in cat_path.iterdir():
            if f.suffix in (".jsonl", ".gz") or f.name.endswith(".jsonl.gz"):
                # Extract date from filename (e.g., app_2024-01-15.jsonl)
                try:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
                    if date_match:
                        file_date = datetime.strptime(
                            date_match.group(1), "%Y-%m-%d"
                        ).replace(tzinfo=timezone.utc)

                        # Filter by date range
                        if start and file_date.date() < start.date():
                            continue
                        if end and file_date.date() > end.date():
                            continue

                    files.append(f)
                except ValueError:
                    # Include files without date pattern (like ingestion session logs)
                    files.append(f)

        return sorted(files, reverse=True)  # Newest first

    def _read_jsonl_file(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """
        Read entries from a JSONL file (supports gzip).
        
        Handles both JSON and plain text log files gracefully.
        Re-runnable and idempotent.
        """
        try:
            if file_path.suffix == ".gz" or file_path.name.endswith(".jsonl.gz"):
                with gzip.open(file_path, "rt", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if line.strip():
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError as e:
                                logger.debug(
                                    f"Skipping non-JSON line {line_num} in {file_path.name}: {e}"
                                )
                                continue
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if line.strip():
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError as e:
                                logger.debug(
                                    f"Skipping non-JSON line {line_num} in {file_path.name}: {e}"
                                )
                                continue
        except Exception as e:
            logger.debug(f"Could not read log file {file_path.name}: {e}")

    def _parse_log_entry(
        self, raw: dict[str, Any], category: LogCategory
    ) -> Optional[LogEntry]:
        """Parse a raw log entry into LogEntry."""
        try:
            # Parse timestamp
            ts_str = raw.get("timestamp")
            if not ts_str:
                return None

            if isinstance(ts_str, str):
                # Handle various timestamp formats
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                return None

            # Extract level (normalize to uppercase)
            level = str(raw.get("level", "INFO")).upper()

            # Extract message
            message = raw.get("message", "")

            # Build extra fields based on category
            extra = {}
            if category == LogCategory.APP:
                for key in ["function", "line", "exception"]:
                    if raw.get(key):
                        extra[key] = raw[key]
            elif category == LogCategory.CHAT:
                for key in ["chat_id", "user_id", "model", "latency_ms", "tokens"]:
                    if raw.get(key):
                        extra[key] = raw[key]
            elif category == LogCategory.AUDIT:
                for key in ["event_type", "user_id", "resource", "action", "success"]:
                    if raw.get(key):
                        extra[key] = raw[key]
            elif category == LogCategory.INGESTION:
                for key in ["ingestion_id", "file_path", "status", "nodes_created", "event_type"]:
                    if raw.get(key):
                        extra[key] = raw[key]

            # Include any other extra fields from raw
            if raw.get("extra"):
                extra.update(raw["extra"])

            return LogEntry(
                timestamp=ts,
                category=category,
                level=level,
                message=message,
                module=raw.get("module") or raw.get("name"),
                request_id=raw.get("request_id"),
                trace_id=raw.get("trace_id"),
                extra=extra if extra else None,
            )
        except Exception as e:
            logger.debug(f"Failed to parse log entry: {e}")
            return None

    def _matches_filter(self, entry: LogEntry, filter: LogFilter) -> bool:
        """Check if a log entry matches the filter criteria."""
        # Level filter (for app logs)
        if filter.level and entry.category == LogCategory.APP:
            entry_priority = LEVEL_PRIORITY.get(LogLevel(entry.level), 0)
            filter_priority = LEVEL_PRIORITY.get(filter.level, 0)
            if entry_priority < filter_priority:
                return False

        # Time range filter
        if filter.start and entry.timestamp < filter.start:
            return False
        if filter.end and entry.timestamp > filter.end:
            return False

        # Module filter (with wildcard support)
        if filter.module and entry.module:
            if filter.module.endswith("*"):
                if not entry.module.startswith(filter.module[:-1]):
                    return False
            elif entry.module != filter.module:
                return False

        # Request ID filter
        if filter.request_id and entry.request_id != filter.request_id:
            return False

        # Ingestion ID filter
        if filter.ingestion_id:
            ingestion_id = entry.extra.get("ingestion_id") if entry.extra else None
            if ingestion_id != filter.ingestion_id:
                return False

        # Chat ID filter
        if filter.chat_id:
            chat_id = entry.extra.get("chat_id") if entry.extra else None
            if chat_id != filter.chat_id:
                return False

        # Full-text search
        if filter.search:
            search_lower = filter.search.lower()
            if search_lower not in entry.message.lower():
                return False

        return True

    def query(self, filter: LogFilter) -> LogQueryResult:
        """Query logs with filters.

        Args:
            filter: Filter criteria

        Returns:
            LogQueryResult with matching entries
        """
        all_entries: list[LogEntry] = []

        # Read logs from each category
        for category in filter.categories:
            files = self._list_log_files(category, filter.start, filter.end)

            for file_path in files:
                for raw in self._read_jsonl_file(file_path):
                    entry = self._parse_log_entry(raw, category)
                    if entry and self._matches_filter(entry, filter):
                        all_entries.append(entry)

        # Sort by timestamp descending
        all_entries.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply pagination
        total_count = len(all_entries)
        paginated = all_entries[filter.offset : filter.offset + filter.limit]
        has_more = filter.offset + filter.limit < total_count

        return LogQueryResult(
            entries=paginated,
            total_count=total_count,
            limit=filter.limit,
            offset=filter.offset,
            has_more=has_more,
        )

    def get_category_stats(self) -> list[CategoryStats]:
        """Get statistics for all log categories."""
        stats = []

        for category in LogCategory:
            cat_path = self._get_category_path(category)
            total_count = 0
            error_count = 0
            oldest: Optional[datetime] = None
            newest: Optional[datetime] = None
            storage_bytes = 0

            if cat_path.exists():
                for file_path in cat_path.iterdir():
                    if file_path.is_file():
                        storage_bytes += file_path.stat().st_size

                        for raw in self._read_jsonl_file(file_path):
                            total_count += 1

                            # Count errors
                            level = str(raw.get("level", "")).upper()
                            if level in ("ERROR", "CRITICAL"):
                                error_count += 1

                            # Track date range
                            ts_str = raw.get("timestamp")
                            if ts_str:
                                try:
                                    ts = datetime.fromisoformat(
                                        ts_str.replace("Z", "+00:00")
                                    )
                                    if oldest is None or ts < oldest:
                                        oldest = ts
                                    if newest is None or ts > newest:
                                        newest = ts
                                except ValueError:
                                    pass

            stats.append(
                CategoryStats(
                    category=category,
                    total_count=total_count,
                    error_count=error_count,
                    oldest=oldest,
                    newest=newest,
                    storage_bytes=storage_bytes,
                )
            )

        return stats

    def get_log_file_path(
        self, category: LogCategory, date: datetime
    ) -> Optional[Path]:
        """Get the path to a specific log file for download.

        Args:
            category: Log category
            date: Date of the log file

        Returns:
            Path to the log file if it exists
        """
        cat_path = self._get_category_path(category)
        date_str = date.strftime("%Y-%m-%d")

        # Check for uncompressed file first
        jsonl_path = cat_path / f"{category.value}_{date_str}.jsonl"
        if jsonl_path.exists():
            return jsonl_path

        # Check for compressed file
        gz_path = cat_path / f"{category.value}_{date_str}.jsonl.gz"
        if gz_path.exists():
            return gz_path

        return None


# Global instance
_log_reader: Optional[UnifiedLogReader] = None


def get_log_reader() -> UnifiedLogReader:
    """Get or create the global log reader instance."""
    global _log_reader
    if _log_reader is None:
        _log_reader = UnifiedLogReader()
    return _log_reader
