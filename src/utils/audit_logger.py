"""
Audit Logger for security and compliance logging.

Provides append-only audit logging for:
- Ingestion events (file uploads, GitHub syncs)
- Query events (chat queries, lineage lookups)
- Admin actions (config changes, deletions)

Logs are stored as append-only JSON files with daily rotation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from enum import Enum

from src.api.config import config

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Ingestion events
    INGESTION_START = "ingestion.start"
    INGESTION_COMPLETE = "ingestion.complete"
    INGESTION_ERROR = "ingestion.error"
    FILE_UPLOAD = "file.upload"
    GITHUB_SYNC = "github.sync"

    # Query events
    CHAT_QUERY = "query.chat"
    LINEAGE_QUERY = "query.lineage"
    DATABASE_QUERY = "query.database"

    # Admin events
    CONFIG_CHANGE = "admin.config_change"
    USER_LOGIN = "admin.login"
    USER_LOGOUT = "admin.logout"
    PROJECT_CREATE = "admin.project_create"
    PROJECT_DELETE = "admin.project_delete"
    DATA_DELETE = "admin.data_delete"


# PII patterns for redaction
PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),  # Email
    (r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b", "[SSN]"),  # SSN
    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD]"),  # Credit card
    (r"\b\d{10,11}\b", "[PHONE]"),  # Phone numbers
]


class AuditLogger:
    """Audit logger for security and compliance.

    Writes audit events to append-only JSON files with daily rotation.
    Supports PII redaction and configurable retention.

    Attributes:
        log_dir: Directory for audit log files.
        retention_days: Number of days to retain logs.
        redact_pii: Whether to redact PII from logs.
    """

    def __init__(
        self,
        log_dir: Optional[str] = None,
        retention_days: int = 90,
        redact_pii: bool = True,
    ):
        """Initialize audit logger.

        Args:
            log_dir: Directory for audit logs (defaults to config.LOG_PATH/audit).
            retention_days: Days to retain logs before archival.
            redact_pii: Whether to redact detected PII.
        """
        self.log_dir = Path(log_dir or os.path.join(config.LOG_PATH, "audit"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.redact_pii = redact_pii
        self._retention_checked = False

        logger.info(f"AuditLogger initialized: {self.log_dir}")

    def _get_log_file(self) -> Path:
        """Get current log file path (daily rotation).

        Returns:
            Path to today's audit log file.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"audit_{today}.jsonl"

    def _redact_pii(self, text: str) -> str:
        """Redact PII patterns from text.

        Args:
            text: Text to redact.

        Returns:
            Text with PII patterns replaced.
        """
        if not self.redact_pii or not text:
            return text

        for pattern, replacement in PII_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def _sanitize_data(self, data: Any) -> Any:
        """Recursively sanitize data for logging.

        Args:
            data: Data to sanitize.

        Returns:
            Sanitized data with PII redacted.
        """
        if isinstance(data, str):
            return self._redact_pii(data)
        elif isinstance(data, dict):
            return {k: self._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        return data

    def log(
        self,
        event_type: AuditEventType,
        user_id: str = "anonymous",
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Write an audit log entry.

        Args:
            event_type: Type of audit event.
            user_id: User who performed the action.
            resource: Resource affected (file path, project_id, etc).
            action: Specific action taken.
            details: Additional event details.
            ip_address: Client IP address.
            success: Whether the action succeeded.
            error_message: Error message if action failed.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        entry = {
            "timestamp": timestamp,
            "event_type": event_type.value,
            "user_id": user_id,
            "resource": self._redact_pii(resource) if resource else None,
            "action": action,
            "details": self._sanitize_data(details) if details else None,
            "ip_address": ip_address,
            "success": success,
            "error": self._redact_pii(error_message) if error_message else None,
        }

        # Remove None values for cleaner logs
        entry = {k: v for k, v in entry.items() if v is not None}

        try:
            log_file = self._get_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            # Run retention once per process lifetime to keep JSONL trimmed
            if not self._retention_checked:
                self._cleanup_old_logs()
                self._retention_checked = True
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def _cleanup_old_logs(self) -> None:
        """Delete audit logs older than retention_days."""
        if self.retention_days <= 0:
            return
        cutoff = datetime.now(timezone.utc).timestamp() - (self.retention_days * 86400)
        for path in self.log_dir.glob("audit_*.jsonl"):
            try:
                # Files named audit_YYYY-MM-DD.jsonl
                date_str = path.stem.replace("audit_", "")
                ts = (
                    datetime.fromisoformat(date_str)
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
                if ts < cutoff:
                    path.unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Skipping audit log cleanup for {path}: {e}")

    # Convenience methods for common events

    def log_ingestion(
        self,
        user_id: str,
        file_path: str,
        project_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log file ingestion event."""
        event_type = (
            AuditEventType.INGESTION_COMPLETE
            if success
            else AuditEventType.INGESTION_ERROR
        )
        self.log(
            event_type=event_type,
            user_id=user_id,
            resource=file_path,
            action="ingest",
            details={"project_id": project_id} if project_id else None,
            ip_address=ip_address,
            success=success,
            error_message=error,
        )

    def log_query(
        self,
        user_id: str,
        query_type: str,
        query_hash: Optional[str] = None,
        latency_ms: Optional[float] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log query event (chat, lineage, database)."""
        event_map = {
            "chat": AuditEventType.CHAT_QUERY,
            "lineage": AuditEventType.LINEAGE_QUERY,
            "database": AuditEventType.DATABASE_QUERY,
        }
        event_type = event_map.get(query_type, AuditEventType.CHAT_QUERY)

        self.log(
            event_type=event_type,
            user_id=user_id,
            action=query_type,
            details={"query_hash": query_hash, "latency_ms": latency_ms},
            ip_address=ip_address,
            success=success,
            error_message=error,
        )

    def log_admin_action(
        self,
        user_id: str,
        action: str,
        resource: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log admin action (config change, deletion, etc)."""
        event_map = {
            "config_change": AuditEventType.CONFIG_CHANGE,
            "login": AuditEventType.USER_LOGIN,
            "logout": AuditEventType.USER_LOGOUT,
            "project_create": AuditEventType.PROJECT_CREATE,
            "project_delete": AuditEventType.PROJECT_DELETE,
            "data_delete": AuditEventType.DATA_DELETE,
        }
        event_type = event_map.get(action, AuditEventType.CONFIG_CHANGE)

        self.log(
            event_type=event_type,
            user_id=user_id,
            resource=resource,
            action=action,
            details=details,
            ip_address=ip_address,
            success=success,
            error_message=error,
        )

    def log_login(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log user login event."""
        self.log(
            event_type=AuditEventType.USER_LOGIN,
            user_id=user_id,
            action="login",
            ip_address=ip_address,
            success=success,
            error_message=error,
        )


# Global audit logger instance
audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance.

    Returns:
        AuditLogger instance.
    """
    global audit_logger
    if audit_logger is None:
        audit_logger = AuditLogger()
    return audit_logger
