import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import ingestion_logs


app = FastAPI()
app.include_router(ingestion_logs.router)
client = TestClient(app)


def test_ingestion_log_not_found():
    with patch("src.api.routers.ingestion_logs.get_tracker") as mock_tracker:
        mock_tracker.return_value.find_log_path.return_value = None
        response = client.get("/api/v1/ingestion/logs/missing")
        assert response.status_code == 404
        assert "Ingestion log not found" in response.json()["detail"]


def test_ingestion_log_json_response(tmp_path: Path):
    ingestion_id = "ingest_123"
    log_path = tmp_path / f"ingestion_{ingestion_id}.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "ingestion_id": ingestion_id,
                "type": "ingestion_started",
                "level": "info",
                "payload": {"total_files": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("src.api.routers.ingestion_logs.get_tracker") as mock_tracker:
        mock_tracker.return_value.find_log_path.return_value = log_path
        response = client.get(f"/api/v1/ingestion/logs/{ingestion_id}?format=json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["ingestion_id"] == ingestion_id
    assert body["events"][0]["type"] == "ingestion_started"
    assert "\n  " in response.text


def test_ingestion_log_jsonl_download(tmp_path: Path):
    ingestion_id = "ingest_456"
    log_path = tmp_path / f"ingestion_{ingestion_id}.jsonl"
    log_path.write_text('{"type":"ingestion_complete"}\n', encoding="utf-8")

    with patch("src.api.routers.ingestion_logs.get_tracker") as mock_tracker:
        mock_tracker.return_value.find_log_path.return_value = log_path
        response = client.get(
            f"/api/v1/ingestion/logs/{ingestion_id}?format=jsonl&download=true"
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")


def test_list_ingestion_logs_empty():
    """Test listing ingestion logs when no index files exist."""
    with patch("src.api.routers.ingestion_logs.config") as mock_config:
        mock_config.STORAGE_PATH = "/tmp/nonexistent"
        response = client.get("/api/v1/ingestion/logs")

    assert response.status_code == 200
    body = response.json()
    assert body["sessions"] == []
    assert body["total"] == 0
    assert body["limit"] == 50


def test_list_ingestion_logs_with_entries(tmp_path: Path):
    """Test listing ingestion logs with multiple index entries."""
    # Create test index files
    project_dir = tmp_path / "TestProject"
    run1_dir = project_dir / "20260109_120000_001_upload"
    run2_dir = project_dir / "20260109_130000_002_github"
    run1_dir.mkdir(parents=True)
    run2_dir.mkdir(parents=True)

    index1 = {
        "ingestion_id": "ingest_001",
        "source": "upload",
        "project_id": "proj_123",
        "project_status": "active",
        "repository_id": "repo_123",
        "run_id": "run_001",
        "status": "completed",
        "started_at": "2026-01-09T12:00:00",
        "completed_at": "2026-01-09T12:05:00",
        "filenames": ["test1.sql", "test2.sql"],
        "source_repo": None,
    }

    index2 = {
        "ingestion_id": "ingest_002",
        "source": "github",
        "project_id": "proj_456",
        "project_status": "active",
        "repository_id": "repo_456",
        "run_id": "run_002",
        "status": "completed_with_errors",
        "started_at": "2026-01-09T13:00:00",
        "completed_at": "2026-01-09T13:10:00",
        "filenames": ["schema.sql"],
        "source_repo": "owner/repo",
    }

    (run1_dir / "ingestion_index.json").write_text(json.dumps(index1))
    (run2_dir / "ingestion_index.json").write_text(json.dumps(index2))

    with patch("src.api.routers.ingestion_logs.config") as mock_config:
        mock_config.STORAGE_PATH = str(tmp_path)
        response = client.get("/api/v1/ingestion/logs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["sessions"]) == 2

    # Should be ordered by most recent (started_at descending)
    assert body["sessions"][0]["ingestion_id"] == "ingest_002"
    assert body["sessions"][1]["ingestion_id"] == "ingest_001"


def test_list_ingestion_logs_with_filters(tmp_path: Path):
    """Test filtering ingestion logs by project_id, source, and status."""
    project_dir = tmp_path / "TestProject"
    run1_dir = project_dir / "20260109_120000_001_upload"
    run2_dir = project_dir / "20260109_130000_002_github"
    run1_dir.mkdir(parents=True)
    run2_dir.mkdir(parents=True)

    index1 = {
        "ingestion_id": "ingest_001",
        "source": "upload",
        "project_id": "proj_123",
        "project_status": "active",
        "repository_id": "repo_123",
        "run_id": "run_001",
        "status": "completed",
        "started_at": "2026-01-09T12:00:00",
        "completed_at": "2026-01-09T12:05:00",
        "filenames": ["test.sql"],
        "source_repo": None,
    }

    index2 = {
        "ingestion_id": "ingest_002",
        "source": "github",
        "project_id": "proj_456",
        "project_status": "active",
        "repository_id": "repo_456",
        "run_id": "run_002",
        "status": "failed",
        "started_at": "2026-01-09T13:00:00",
        "completed_at": "2026-01-09T13:10:00",
        "filenames": ["schema.sql"],
        "source_repo": "owner/repo",
    }

    (run1_dir / "ingestion_index.json").write_text(json.dumps(index1))
    (run2_dir / "ingestion_index.json").write_text(json.dumps(index2))

    with patch("src.api.routers.ingestion_logs.config") as mock_config:
        mock_config.STORAGE_PATH = str(tmp_path)

        # Filter by source
        response = client.get("/api/v1/ingestion/logs?source=upload")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sessions"][0]["source"] == "upload"

        # Filter by project_id
        response = client.get("/api/v1/ingestion/logs?project_id=proj_456")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sessions"][0]["project_id"] == "proj_456"

        # Filter by status
        response = client.get("/api/v1/ingestion/logs?status=failed")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sessions"][0]["status"] == "failed"


def test_list_ingestion_logs_with_limit(tmp_path: Path):
    """Test limit parameter for pagination."""
    project_dir = tmp_path / "TestProject"

    # Create 5 index files
    for i in range(5):
        run_dir = project_dir / f"2026010912{i:02d}00_{i:03d}_upload"
        run_dir.mkdir(parents=True)

        index = {
            "ingestion_id": f"ingest_{i:03d}",
            "source": "upload",
            "project_id": "proj_123",
            "project_status": "active",
            "repository_id": "repo_123",
            "run_id": f"run_{i:03d}",
            "status": "completed",
            "started_at": f"2026-01-09T12:{i:02d}:00",
            "completed_at": f"2026-01-09T12:{i:02d}:30",
            "filenames": [f"test{i}.sql"],
            "source_repo": None,
        }
        (run_dir / "ingestion_index.json").write_text(json.dumps(index))

    with patch("src.api.routers.ingestion_logs.config") as mock_config:
        mock_config.STORAGE_PATH = str(tmp_path)
        response = client.get("/api/v1/ingestion/logs?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["sessions"]) == 2
    assert body["limit"] == 2


def test_stage_event_logging(tmp_path: Path):
    """Test that stage events are properly logged."""
    from src.services.ingestion_tracker import IngestionTracker
    import asyncio

    async def run_test():
        tracker = IngestionTracker()
        log_dir = tmp_path / "test_run"
        log_dir.mkdir(parents=True)

        session = await tracker.start_session(
            source="upload",
            project_id="proj_123",
            repository_id="repo_123",
            file_paths=["test.sql"],
            log_dir=log_dir,
        )

        # Log parsing stage
        await tracker.log_stage(
            ingestion_id=session.ingestion_id,
            stage="parsing",
            status="started",
            file_path="test.sql",
        )

        await tracker.log_stage(
            ingestion_id=session.ingestion_id,
            stage="parsing",
            status="completed",
            file_path="test.sql",
            summary={"nodes_created": 5},
        )

        # Verify log file contains stage events
        log_path = log_dir / f"ingestion_{session.ingestion_id}.jsonl"
        assert log_path.exists()

        events = []
        with log_path.open("r") as f:
            for line in f:
                events.append(json.loads(line))

        stage_events = [e for e in events if e["type"] == "stage_event"]
        assert len(stage_events) == 2
        assert stage_events[0]["payload"]["stage"] == "parsing"
        assert stage_events[0]["payload"]["status"] == "started"
        assert stage_events[1]["payload"]["status"] == "completed"
        assert stage_events[1]["payload"]["summary"]["nodes_created"] == 5

    asyncio.run(run_test())
