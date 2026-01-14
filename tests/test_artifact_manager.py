"""
Unit tests for ArtifactManager service.

Tests run creation, file versioning, content hashing, and deduplication logic.
"""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from src.storage import ArtifactManager
from src.storage.duckdb_client import initialize_duckdb, close_duckdb
from src.storage.metadata_store import ProjectStore


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def duckdb_client():
    """Initialize in-memory DuckDB for tests."""
    client = initialize_duckdb(":memory:")
    yield client
    close_duckdb()


@pytest_asyncio.fixture
async def test_project(duckdb_client):
    """Create a test project."""
    project_store = ProjectStore()
    project = await project_store.create(
        name="TestProject", description="Test project for artifact manager"
    )
    return project


class TestArtifactManager:
    """Test ArtifactManager functionality."""

    @pytest.mark.asyncio
    async def test_create_run(self, temp_data_dir, duckdb_client, test_project):
        """Test creating a run directory."""
        manager = ArtifactManager(base_path=temp_data_dir)

        context = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="initial_ingest",
        )

        # Check context properties
        assert context.run_id is not None
        assert context.project_id == test_project["id"]
        assert context.project_name == test_project["name"]
        assert context.action == "initial_ingest"
        assert context.timestamp is not None
        assert context.sequence == 1

        # Check directory was created
        assert context.run_dir.exists()
        assert context.run_dir.is_dir()

        # Check run was tracked in database
        metadata = manager.get_run_metadata(context.run_id)
        assert metadata is not None
        assert metadata.status == "in_progress"

    @pytest.mark.asyncio
    async def test_concurrent_runs_sequence(
        self, temp_data_dir, duckdb_client, test_project
    ):
        """Test sequence numbering for concurrent runs."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # Create multiple runs with same timestamp (simulating concurrent runs)
        context1 = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="run1",
        )

        # Force same timestamp by creating immediately
        context2 = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="run2",
        )

        # Sequences should be different (or timestamps differ)
        if context1.timestamp == context2.timestamp:
            assert context2.sequence == context1.sequence + 1

        # Both directories should exist
        assert context1.run_dir.exists()
        assert context2.run_dir.exists()

    @pytest.mark.asyncio
    async def test_get_artifact_path(self, temp_data_dir, duckdb_client, test_project):
        """Test getting artifact paths."""
        manager = ArtifactManager(base_path=temp_data_dir)

        context = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="test",
        )

        # Get artifact path
        raw_path = manager.get_artifact_path(context.run_id, "raw_source")
        assert raw_path is not None
        assert raw_path.exists()
        assert raw_path.name == "raw_source"

        # Get another artifact type
        embeddings_path = manager.get_artifact_path(context.run_id, "sql_embeddings")
        assert embeddings_path is not None
        assert embeddings_path.exists()
        assert embeddings_path.name == "sql_embeddings"

    @pytest.mark.asyncio
    async def test_list_runs(self, temp_data_dir, duckdb_client, test_project):
        """Test listing runs for a project."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # Create multiple runs
        await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="run1",
        )

        await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="run2",
        )

        # List runs
        runs = manager.list_runs(test_project["id"])
        assert len(runs) == 2

        # Should be ordered by timestamp desc
        assert runs[0].action in ("run1", "run2")
        assert runs[1].action in ("run1", "run2")

    @pytest.mark.asyncio
    async def test_complete_run(self, temp_data_dir, duckdb_client, test_project):
        """Test marking run as completed."""
        manager = ArtifactManager(base_path=temp_data_dir)

        context = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="test",
        )

        # Complete the run
        success = await manager.complete_run(context.run_id, status="completed")
        assert success is True

        # Check status updated
        metadata = manager.get_run_metadata(context.run_id)
        assert metadata.status == "completed"
        assert metadata.completed_at is not None

    @pytest.mark.asyncio
    async def test_file_registration_new(
        self, temp_data_dir, duckdb_client, test_project
    ):
        """Test registering a new file."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # Create run and artifact directory
        context = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="test",
        )

        raw_dir = manager.get_artifact_path(context.run_id, "raw_source")

        # Create test file
        test_file = raw_dir / "test.sql"
        test_file.write_text("SELECT * FROM users;")

        # Register file
        result = await manager.register_file(
            project_id=test_project["id"],
            run_id=context.run_id,
            filename="test.sql",
            file_path=test_file,
        )

        assert result["status"] == "new_file"
        assert result["file_id"] is not None
        assert result["file_hash"] is not None
        assert result["skip_processing"] is False
        assert len(result["file_hash"]) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_file_versioning_different_content(
        self, temp_data_dir, duckdb_client, test_project
    ):
        """Test file versioning when content changes."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # First upload
        context1 = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="upload1",
        )

        raw_dir1 = manager.get_artifact_path(context1.run_id, "raw_source")
        file1 = raw_dir1 / "schema.sql"
        file1.write_text("SELECT * FROM users;")

        result1 = await manager.register_file(
            project_id=test_project["id"],
            run_id=context1.run_id,
            filename="schema.sql",
            file_path=file1,
        )

        assert result1["status"] == "new_file"
        hash1 = result1["file_hash"]

        # Second upload with different content
        context2 = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="upload2",
        )

        raw_dir2 = manager.get_artifact_path(context2.run_id, "raw_source")
        file2 = raw_dir2 / "schema.sql"
        file2.write_text("SELECT * FROM users WHERE active = true;")

        result2 = await manager.register_file(
            project_id=test_project["id"],
            run_id=context2.run_id,
            filename="schema.sql",
            file_path=file2,
        )

        assert result2["status"] == "new_version"
        assert result2["superseded_previous"] is True
        assert result2["file_hash"] != hash1  # Different content = different hash

        # Check first version is marked as superseded
        history = manager.get_file_history(test_project["id"], "schema.sql")
        assert len(history) == 2

        # Newest first
        assert history[0].is_superseded is False
        assert history[1].is_superseded is True
        assert history[1].superseded_by == context2.run_id

    @pytest.mark.asyncio
    async def test_content_deduplication(
        self, temp_data_dir, duckdb_client, test_project
    ):
        """Test content-based deduplication with identical files."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # First upload
        context1 = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="upload1",
        )

        raw_dir1 = manager.get_artifact_path(context1.run_id, "raw_source")
        file1 = raw_dir1 / "data.sql"
        file1.write_text("SELECT * FROM products;")

        result1 = await manager.register_file(
            project_id=test_project["id"],
            run_id=context1.run_id,
            filename="data.sql",
            file_path=file1,
        )

        assert result1["status"] == "new_file"
        hash1 = result1["file_hash"]

        # Second upload with IDENTICAL content
        context2 = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="upload2",
        )

        raw_dir2 = manager.get_artifact_path(context2.run_id, "raw_source")
        file2 = raw_dir2 / "data.sql"
        file2.write_text("SELECT * FROM products;")  # Same content

        result2 = await manager.register_file(
            project_id=test_project["id"],
            run_id=context2.run_id,
            filename="data.sql",
            file_path=file2,
        )

        # Should detect duplicate and skip processing
        assert result2["status"] == "duplicate"
        assert result2["skip_processing"] is True
        assert result2["file_hash"] == hash1
        assert result2["existing_run_id"] == context1.run_id

    @pytest.mark.asyncio
    async def test_get_latest_file(self, temp_data_dir, duckdb_client, test_project):
        """Test getting latest file version."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # Upload multiple versions
        for i in range(3):
            context = await manager.create_run(
                project_id=test_project["id"],
                project_name=test_project["name"],
                action=f"upload{i+1}",
            )

            raw_dir = manager.get_artifact_path(context.run_id, "raw_source")
            file = raw_dir / "report.sql"
            file.write_text(f"SELECT * FROM data WHERE version = {i+1};")

            await manager.register_file(
                project_id=test_project["id"],
                run_id=context.run_id,
                filename="report.sql",
                file_path=file,
            )

        # Get latest version
        latest = manager.get_latest_file(test_project["id"], "report.sql")
        assert latest is not None
        assert latest.is_superseded is False

        # Content should be from version 3
        latest_content = Path(latest.file_path).read_text()
        assert "version = 3" in latest_content

    @pytest.mark.asyncio
    async def test_get_file_history(self, temp_data_dir, duckdb_client, test_project):
        """Test getting file version history."""
        manager = ArtifactManager(base_path=temp_data_dir)

        # Upload 3 versions
        for i in range(3):
            context = await manager.create_run(
                project_id=test_project["id"],
                project_name=test_project["name"],
                action=f"upload{i+1}",
            )

            raw_dir = manager.get_artifact_path(context.run_id, "raw_source")
            file = raw_dir / "changelog.sql"
            file.write_text(f"-- Version {i+1}")

            await manager.register_file(
                project_id=test_project["id"],
                run_id=context.run_id,
                filename="changelog.sql",
                file_path=file,
            )

        # Get history
        history = manager.get_file_history(test_project["id"], "changelog.sql")
        assert len(history) == 3

        # Should be ordered newest first
        assert history[0].is_superseded is False  # Latest version
        assert history[1].is_superseded is True  # Superseded
        assert history[2].is_superseded is True  # Superseded

    @pytest.mark.asyncio
    async def test_mark_file_processed(
        self, temp_data_dir, duckdb_client, test_project
    ):
        """Test marking file as processed."""
        manager = ArtifactManager(base_path=temp_data_dir)

        context = await manager.create_run(
            project_id=test_project["id"],
            project_name=test_project["name"],
            action="test",
        )

        raw_dir = manager.get_artifact_path(context.run_id, "raw_source")
        test_file = raw_dir / "test.sql"
        test_file.write_text("SELECT 1;")

        result = await manager.register_file(
            project_id=test_project["id"],
            run_id=context.run_id,
            filename="test.sql",
            file_path=test_file,
        )

        file_id = result["file_id"]

        # Mark as processed
        await manager.mark_file_processed(file_id)

        # Check processed_at is set
        latest = manager.get_latest_file(test_project["id"], "test.sql")
        assert latest.processed_at is not None

    @pytest.mark.asyncio
    async def test_project_name_sanitization(self, temp_data_dir, duckdb_client):
        """Test project name sanitization for filesystem."""
        project_store = ProjectStore()
        project = await project_store.create(
            name="Test/Project\\With:Invalid*Chars?",
            description="Test special characters",
        )

        manager = ArtifactManager(base_path=temp_data_dir)

        context = await manager.create_run(
            project_id=project["id"], project_name=project["name"], action="test"
        )

        # Directory should be created with sanitized name
        assert context.run_dir.exists()

        # Check the project directory name (not the full path)
        project_dir_name = context.run_dir.parent.name

        # Sanitized name should not contain special chars (except underscores which replace them)
        assert "/" not in project_dir_name
        assert "*" not in project_dir_name
        assert "?" not in project_dir_name
        # Verify it was actually sanitized
        assert "_" in project_dir_name  # Special chars replaced with underscores


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
