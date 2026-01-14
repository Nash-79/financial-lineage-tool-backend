"""Tests for audit logger functionality."""

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone


from src.utils.audit_logger import AuditLogger, AuditEventType


def test_audit_logger_writes_and_redacts(tmp_path: Path):
    """Test basic logging and PII redaction."""
    logger = AuditLogger(log_dir=tmp_path, retention_days=1, redact_pii=True)
    logger.log(
        event_type=AuditEventType.CHAT_QUERY,
        user_id="user123",
        resource="user@example.com",
        details={"note": "call me at 5551234567"},
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    assert files, "audit log file should be created"
    line = files[0].read_text().strip()
    payload = json.loads(line)
    assert payload["user_id"] == "user123"
    assert payload["resource"] == "[EMAIL]"
    assert "[PHONE]" in payload["details"]["note"]


def test_audit_logger_retention(tmp_path: Path):
    """Test retention policy with retention_days=0 (no cleanup)."""
    logger = AuditLogger(log_dir=tmp_path, retention_days=0, redact_pii=False)
    # create an old file manually
    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    old_file = tmp_path / f"audit_{old_date}.jsonl"
    old_file.write_text("{}\n")

    logger.log(
        event_type=AuditEventType.USER_LOGIN,
        user_id="user123",
    )

    # With retention_days=0, cleanup should be a no-op; file stays
    assert old_file.exists()


def test_audit_logger_retention_cleanup(tmp_path: Path):
    """Test that old log files are deleted based on retention policy."""
    logger = AuditLogger(log_dir=tmp_path, retention_days=7, redact_pii=False)

    # Create old file (30 days ago - should be deleted)
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    old_file = tmp_path / f"audit_{old_date}.jsonl"
    old_file.write_text('{"test":"old"}\n')

    # Create recent file (2 days ago - should be kept)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    recent_file = tmp_path / f"audit_{recent_date}.jsonl"
    recent_file.write_text('{"test":"recent"}\n')

    # Write a log to trigger cleanup
    logger.log(
        event_type=AuditEventType.USER_LOGIN,
        user_id="user123",
    )

    # Old file should be deleted, recent file should remain
    assert not old_file.exists(), "Old log file should be deleted"
    assert recent_file.exists(), "Recent log file should be kept"


def test_pii_redaction_email(tmp_path: Path):
    """Test email redaction."""
    logger = AuditLogger(log_dir=tmp_path, redact_pii=True)
    logger.log(
        event_type=AuditEventType.CHAT_QUERY,
        user_id="test",
        resource="Contact john.doe@example.com for details",
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)
    assert "[EMAIL]" in payload["resource"]
    assert "john.doe@example.com" not in payload["resource"]


def test_pii_redaction_ssn(tmp_path: Path):
    """Test SSN redaction."""
    logger = AuditLogger(log_dir=tmp_path, redact_pii=True)
    logger.log(
        event_type=AuditEventType.INGESTION_COMPLETE,
        user_id="test",
        details={"ssn": "123-45-6789"},
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)
    assert "[SSN]" in payload["details"]["ssn"]
    assert "123-45-6789" not in payload["details"]["ssn"]


def test_pii_redaction_credit_card(tmp_path: Path):
    """Test credit card redaction."""
    logger = AuditLogger(log_dir=tmp_path, redact_pii=True)
    logger.log(
        event_type=AuditEventType.CONFIG_CHANGE,
        user_id="test",
        details={"card": "Card number: 1234 5678 9012 3456"},
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)
    assert "[CARD]" in payload["details"]["card"]
    assert "1234 5678 9012 3456" not in payload["details"]["card"]


def test_pii_redaction_disabled(tmp_path: Path):
    """Test that PII is not redacted when redact_pii=False."""
    logger = AuditLogger(log_dir=tmp_path, redact_pii=False)
    logger.log(
        event_type=AuditEventType.CHAT_QUERY,
        user_id="test",
        resource="user@example.com",
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)
    assert payload["resource"] == "user@example.com"


def test_log_login_success(tmp_path: Path):
    """Test log_login convenience method for successful login."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_login(user_id="alice", ip_address="192.168.1.1", success=True)

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "admin.login"
    assert payload["user_id"] == "alice"
    assert payload["ip_address"] == "192.168.1.1"
    assert payload["success"] is True
    assert "error" not in payload


def test_log_login_failure(tmp_path: Path):
    """Test log_login convenience method for failed login."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_login(
        user_id="bob", ip_address="10.0.0.1", success=False, error="Invalid credentials"
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "admin.login"
    assert payload["user_id"] == "bob"
    assert payload["success"] is False
    assert payload["error"] == "Invalid credentials"


def test_log_query(tmp_path: Path):
    """Test log_query convenience method."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_query(
        user_id="user1",
        query_type="chat",
        query_hash="abc123",
        latency_ms=150.5,
        ip_address="127.0.0.1",
        success=True,
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "query.chat"
    assert payload["user_id"] == "user1"
    assert payload["details"]["query_hash"] == "abc123"
    assert payload["details"]["latency_ms"] == 150.5
    assert payload["ip_address"] == "127.0.0.1"


def test_log_query_lineage(tmp_path: Path):
    """Test log_query with lineage query type."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_query(
        user_id="user2",
        query_type="lineage",
        latency_ms=200.0,
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "query.lineage"


def test_log_ingestion_success(tmp_path: Path):
    """Test log_ingestion convenience method for successful ingestion."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_ingestion(
        user_id="ingester",
        file_path="/path/to/file.sql",
        project_id="proj123",
        success=True,
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "ingestion.complete"
    assert payload["user_id"] == "ingester"
    assert payload["resource"] == "/path/to/file.sql"
    assert payload["details"]["project_id"] == "proj123"
    assert payload["success"] is True


def test_log_ingestion_failure(tmp_path: Path):
    """Test log_ingestion convenience method for failed ingestion."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_ingestion(
        user_id="ingester",
        file_path="/path/to/bad.sql",
        success=False,
        error="Parse error",
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "ingestion.error"
    assert payload["success"] is False
    assert payload["error"] == "Parse error"


def test_log_admin_action(tmp_path: Path):
    """Test log_admin_action convenience method."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log_admin_action(
        user_id="admin",
        action="project_delete",
        resource="project_xyz",
        details={"reason": "test cleanup"},
        success=True,
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert payload["event_type"] == "admin.project_delete"
    assert payload["user_id"] == "admin"
    assert payload["resource"] == "project_xyz"
    assert payload["details"]["reason"] == "test cleanup"


def test_daily_log_rotation(tmp_path: Path):
    """Test that logs are written to daily files."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log(event_type=AuditEventType.USER_LOGIN, user_id="test")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expected_file = tmp_path / f"audit_{today}.jsonl"

    assert expected_file.exists(), "Log file should be named with today's date"


def test_none_values_removed(tmp_path: Path):
    """Test that None values are removed from log entries."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log(
        event_type=AuditEventType.CHAT_QUERY,
        user_id="test",
        resource=None,  # This should not appear in log
        details=None,  # This should not appear in log
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert "resource" not in payload
    assert "details" not in payload
    assert "user_id" in payload  # Non-None values should still be present


def test_recursive_pii_sanitization(tmp_path: Path):
    """Test that PII redaction works recursively in nested data."""
    logger = AuditLogger(log_dir=tmp_path, redact_pii=True)
    logger.log(
        event_type=AuditEventType.CHAT_QUERY,
        user_id="test",
        details={
            "nested": {
                "email": "secret@example.com",
                "list": ["call 1234567890", "safe text"],
            }
        },
    )

    files = list(tmp_path.glob("audit_*.jsonl"))
    line = files[0].read_text().strip()
    payload = json.loads(line)

    assert "[EMAIL]" in payload["details"]["nested"]["email"]
    assert "[PHONE]" in payload["details"]["nested"]["list"][0]
    assert "safe text" in payload["details"]["nested"]["list"][1]


def test_multiple_logs_append(tmp_path: Path):
    """Test that multiple logs append to the same file."""
    logger = AuditLogger(log_dir=tmp_path)
    logger.log(event_type=AuditEventType.USER_LOGIN, user_id="user1")
    logger.log(event_type=AuditEventType.USER_LOGOUT, user_id="user2")

    files = list(tmp_path.glob("audit_*.jsonl"))
    assert len(files) == 1, "Should only have one log file for today"

    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 2, "Should have two log entries"

    log1 = json.loads(lines[0])
    log2 = json.loads(lines[1])

    assert log1["user_id"] == "user1"
    assert log2["user_id"] == "user2"


def test_get_audit_logger_singleton(tmp_path: Path):
    """Test that get_audit_logger returns a singleton instance."""
    from src.utils.audit_logger import get_audit_logger

    # Reset global instance
    import src.utils.audit_logger as module

    module.audit_logger = None

    logger1 = get_audit_logger()
    logger2 = get_audit_logger()

    assert logger1 is logger2, "Should return the same instance"
