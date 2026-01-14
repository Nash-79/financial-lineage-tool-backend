from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main_local import app
from src.storage.artifact_manager import ArtifactManager
from src.storage.metadata_store import ensure_default_project


@pytest.mark.asyncio
async def test_file_metadata_persists_and_exposes_expected_fields(tmp_path: Path):
    """Register a file and ensure metadata surfaces via file endpoints."""
    project = await ensure_default_project()

    artifact_manager = ArtifactManager(base_path=str(tmp_path))
    run = await artifact_manager.create_run(
        project_id=project["id"],
        project_name=project["name"],
        action="test_ingestion",
    )

    file_path = tmp_path / "raw_source" / "nested" / "demo.sql"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("select 1;")

    registration = await artifact_manager.register_file(
        project_id=project["id"],
        run_id=run.run_id,
        filename="demo.sql",
        file_path=file_path,
        relative_path="nested/demo.sql",
        file_type="sql",
        source="upload",
        repository_id="repo-local",
        status="processed",
    )
    await artifact_manager.update_file_status(registration["file_id"], "processed")

    client = TestClient(app)

    list_response = client.get(
        "/api/v1/files",
        params={"project_id": project["id"], "limit": 50},
    )
    assert list_response.status_code == 200
    files = list_response.json()

    assert any(
        f.get("file_id") == registration["file_id"]
        and f.get("relative_path") == "nested/demo.sql"
        and f.get("file_type") == "sql"
        and f.get("source") == "upload"
        and f.get("project_id") == project["id"]
        for f in files
    ), "Registered file metadata should be returned by list endpoint"

    stats_response = client.get(
        "/api/v1/files/stats",
        params={"project_id": project["id"]},
    )
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert "total" in stats
    assert stats.get("total", 0) >= 1
