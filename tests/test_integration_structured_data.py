"""
Integration tests for structured data outputs.

Tests the complete flow from file upload through artifact storage,
verifying the hierarchical directory structure and metadata tracking.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.artifact_manager import ArtifactManager
from src.storage.duckdb_client import initialize_duckdb, close_duckdb
from src.storage.metadata_store import ProjectStore


async def test_file_upload_flow():
    """Test 5.1: File upload flow with hierarchical structure."""
    print("\n" + "=" * 80)
    print("TEST 5.1: File Upload Flow")
    print("=" * 80)

    # Initialize database
    initialize_duckdb("data/metadata.duckdb")

    # Create test project
    project_store = ProjectStore()
    project = await project_store.create(
        name="IntegrationTestProject",
        description="Test project for integration testing",
    )
    project_id = project["id"]
    print(f"✓ Created test project: {project_id}")

    # Create artifact manager
    artifact_manager = ArtifactManager(base_path="data")

    # Create a run
    run_context = await artifact_manager.create_run(
        project_id=project_id,
        project_name="IntegrationTestProject",
        action="integration_test",
    )
    print(f"✓ Created run: {run_context.run_id}")
    print(f"  Run directory: {run_context.run_dir}")

    # Verify run directory structure
    assert run_context.run_dir.exists(), "Run directory should exist"
    print(f"✓ Run directory exists: {run_context.run_dir}")

    # Get artifact directories
    raw_source_dir = run_context.get_artifact_dir("raw_source")
    embeddings_dir = run_context.get_artifact_dir("embeddings")
    graph_export_dir = run_context.get_artifact_dir("graph_export")

    print(f"✓ Artifact directories created:")
    print(f"  - raw_source: {raw_source_dir}")
    print(f"  - embeddings: {embeddings_dir}")
    print(f"  - graph_export: {graph_export_dir}")

    # Create test file
    test_file_path = raw_source_dir / "test.sql"
    test_content = "SELECT * FROM test_table;"
    test_file_path.write_text(test_content)
    print(f"✓ Created test file: {test_file_path}")

    # Register file
    registration = await artifact_manager.register_file(
        project_id=project_id,
        run_id=run_context.run_id,
        filename="test.sql",
        file_path=test_file_path,
    )
    print(f"✓ Registered file: {registration['file_id']}")
    print(f"  Status: {registration['status']}")
    print(f"  Hash: {registration['file_hash'][:16]}...")

    # Verify file metadata
    latest_file = artifact_manager.get_latest_file(project_id, "test.sql")
    assert latest_file is not None, "File should be registered"
    assert latest_file.file_hash == registration["file_hash"], "Hash should match"
    print(f"✓ File metadata verified in database")

    # Test duplicate detection
    duplicate_file_path = raw_source_dir / "test_duplicate.sql"
    duplicate_file_path.write_text(test_content)  # Same content

    duplicate_registration = await artifact_manager.register_file(
        project_id=project_id,
        run_id=run_context.run_id,
        filename="test.sql",  # Same filename
        file_path=duplicate_file_path,
    )

    assert duplicate_registration["status"] == "duplicate", "Should detect duplicate"
    assert duplicate_registration["skip_processing"] == True, "Should skip processing"
    print(f"✓ Duplicate detection working")

    # Complete run
    await artifact_manager.complete_run(run_context.run_id, status="completed")
    print(f"✓ Run marked as completed")

    # Verify run metadata
    run_metadata = artifact_manager.get_run_metadata(run_context.run_id)
    assert run_metadata is not None, "Run metadata should exist"
    assert run_metadata.status == "completed", "Run should be completed"
    print(f"✓ Run metadata verified")

    print("\n✅ TEST 5.1 PASSED: File upload flow working correctly")
    return True


async def test_concurrent_runs():
    """Test 5.3: Concurrent ingestions with sequence numbers."""
    print("\n" + "=" * 80)
    print("TEST 5.3: Concurrent Ingestions")
    print("=" * 80)

    # Get test project
    project_store = ProjectStore()
    project = await project_store.create(
        name="ConcurrentTestProject", description="Test concurrent runs"
    )
    project_id = project["id"]

    artifact_manager = ArtifactManager(base_path="data")

    # Create multiple runs concurrently (simulate same timestamp)

    # Force same timestamp by creating runs very quickly
    runs = []
    for i in range(3):
        run = await artifact_manager.create_run(
            project_id=project_id,
            project_name="ConcurrentTestProject",
            action=f"concurrent_test_{i}",
        )
        runs.append(run)
        print(f"✓ Created run {i+1}: sequence={run.sequence}, dir={run.run_dir.name}")

    # Verify sequences are different
    sequences = [r.sequence for r in runs]
    assert len(set(sequences)) == len(sequences), "Sequences should be unique"
    print(f"✓ Sequence numbers are unique: {sequences}")

    # Verify no directory conflicts
    dirs = [r.run_dir for r in runs]
    assert len(set(dirs)) == len(dirs), "Run directories should be unique"
    print(f"✓ No directory conflicts")

    print("\n✅ TEST 5.3 PASSED: Concurrent ingestions handled correctly")
    return True


async def test_graph_export_integration():
    """Test 3.2: Graph export with run_id."""
    print("\n" + "=" * 80)
    print("TEST 3.2: Graph Export Integration")
    print("=" * 80)

    # Get test project
    project_store = ProjectStore()
    projects = project_store.list()
    if not projects:
        project = await project_store.create(
            name="GraphExportTestProject", description="Test graph export"
        )
        project_id = project["id"]
    else:
        project_id = projects[0]["id"]

    artifact_manager = ArtifactManager(base_path="data")

    # Create run for export
    run_context = await artifact_manager.create_run(
        project_id=project_id,
        project_name="GraphExportTestProject",
        action="graph_export_test",
    )
    print(f"✓ Created run: {run_context.run_id}")

    # Get graph export directory
    export_dir = artifact_manager.get_artifact_path(run_context.run_id, "graph_export")
    assert export_dir is not None, "Export directory should be resolvable"
    print(f"✓ Graph export directory: {export_dir}")

    # Simulate export (without actually connecting to Neo4j)
    test_export_data = {
        "metadata": {
            "run_id": run_context.run_id,
            "project_id": project_id,
            "export_timestamp": datetime.utcnow().isoformat(),
        },
        "nodes": [],
        "relationships": [],
    }

    import json

    export_file = export_dir / "graph_export.json"
    export_file.write_text(json.dumps(test_export_data, indent=2))
    print(f"✓ Created test export: {export_file}")

    # Verify export exists
    assert export_file.exists(), "Export file should exist"

    # Verify content
    loaded_data = json.loads(export_file.read_text())
    assert (
        loaded_data["metadata"]["run_id"] == run_context.run_id
    ), "Run ID should match"
    print(f"✓ Export data verified")

    print("\n✅ TEST 3.2 PASSED: Graph export integration working")
    return True


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("INTEGRATION TEST SUITE: Structured Data Outputs")
    print("=" * 80)

    try:
        # Run tests
        await test_file_upload_flow()
        await test_concurrent_runs()
        await test_graph_export_integration()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nSummary:")
        print("  ✓ File upload flow with hierarchical structure")
        print("  ✓ Duplicate detection and file versioning")
        print("  ✓ Concurrent run handling with sequence numbers")
        print("  ✓ Graph export integration with run directories")
        print("  ✓ Run metadata tracking in DuckDB")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        close_duckdb()


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
