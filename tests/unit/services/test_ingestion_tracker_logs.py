import json
from pathlib import Path

import pytest

from src.services.ingestion_tracker import IngestionTracker, FileStatus


@pytest.mark.asyncio
async def test_ingestion_tracker_writes_jsonl_logs(tmp_path: Path):
    tracker = IngestionTracker()
    session = await tracker.start_session(
        source="upload",
        project_id="proj_1",
        repository_id="repo_1",
        file_paths=["file.sql"],
        log_dir=tmp_path,
        verbose=True,
    )

    await tracker.update_file_status(
        session.ingestion_id, "file.sql", FileStatus.DOWNLOADING
    )
    await tracker.file_complete(session.ingestion_id, "file.sql", nodes_created=2)
    await tracker.complete_session(session.ingestion_id)

    log_path = tmp_path / f"ingestion_{session.ingestion_id}.jsonl"
    assert log_path.exists()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert any(json.loads(line)["type"] == "ingestion_started" for line in lines)
    assert any(json.loads(line)["type"] == "ingestion_complete" for line in lines)
