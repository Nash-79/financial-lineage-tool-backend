"""
Integration tests for DataPathManager and hierarchical data structure.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.utils.data_paths import (
    DataPathManager,
    normalize_database_name,
    detect_database_name,
    get_path_manager
)


class TestDatabaseNameNormalization:
    """Test database name normalization."""

    def test_normalize_adventureworks(self):
        # "AdventureWorksLT-All" becomes "adventureworkslt-all" (no hyphen between "works" and "lt")
        assert normalize_database_name("AdventureWorksLT-All") == "adventureworkslt-all"

    def test_normalize_underscores(self):
        assert normalize_database_name("sample_financial_schema") == "sample-financial-schema"

    def test_normalize_spaces(self):
        assert normalize_database_name("My Database 123") == "my-database-123"

    def test_normalize_mixed(self):
        assert normalize_database_name("Test__DB--Name") == "test-db-name"

    def test_normalize_already_normalized(self):
        assert normalize_database_name("my-database") == "my-database"


class TestDatabaseNameDetection:
    """Test database name detection from file paths."""

    def test_detect_from_hyphenated_filename(self):
        assert detect_database_name("AdventureWorksLT-All.sql") == "adventureworkslt"

    def test_detect_from_underscored_filename(self):
        assert detect_database_name("sample_financial_schema.sql") == "sample"

    def test_detect_with_explicit_name(self):
        assert detect_database_name("any_file.sql", explicit_name="MyDB") == "mydb"

    def test_detect_defaults_to_default(self):
        # File with no separator should default to "default"
        assert detect_database_name("schema.sql") == "default"


class TestDataPathManager:
    """Test DataPathManager functionality."""

    @pytest.fixture
    def temp_data_root(self):
        """Create a temporary data directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_initialization(self, temp_data_root):
        """Test DataPathManager initialization."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        assert paths.data_root == temp_data_root
        assert paths.database_name == "test-db"
        assert paths.database_dir == temp_data_root / "test-db"

    def test_get_category_paths(self, temp_data_root):
        """Test getting category paths."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        raw_path = paths.get_category_path("raw")
        assert raw_path == temp_data_root / "test-db" / "raw"
        assert raw_path.exists()  # Should be created automatically

        separated_path = paths.get_category_path("separated")
        assert separated_path == temp_data_root / "test-db" / "separated"
        assert separated_path.exists()

    def test_raw_path(self, temp_data_root):
        """Test raw file path construction."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        raw_file = paths.raw_path("schema.sql")
        assert raw_file == temp_data_root / "test-db" / "raw" / "schema.sql"
        assert raw_file.parent.exists()

    def test_separated_path(self, temp_data_root):
        """Test separated SQL paths."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        tables_dir = paths.separated_path("tables")
        assert tables_dir == temp_data_root / "test-db" / "separated" / "tables"
        assert tables_dir.exists()

        customer_table = paths.separated_path("tables", "Customer.sql")
        assert customer_table == temp_data_root / "test-db" / "separated" / "tables" / "Customer.sql"

    def test_embeddings_path(self, temp_data_root):
        """Test embeddings path construction."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        emb_file = paths.embeddings_path("sql_embeddings.json")
        assert emb_file == temp_data_root / "test-db" / "embeddings" / "sql_embeddings.json"
        assert emb_file.parent.exists()

    def test_graph_path(self, temp_data_root):
        """Test graph export path construction."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        graph_file = paths.graph_path("graph_export.json")
        assert graph_file == temp_data_root / "test-db" / "graph" / "graph_export.json"
        assert graph_file.parent.exists()

    def test_metadata_path(self, temp_data_root):
        """Test metadata path construction."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        log_file = paths.metadata_path("failed_ingestion.jsonl")
        assert log_file == temp_data_root / "test-db" / "metadata" / "failed_ingestion.jsonl"
        assert log_file.parent.exists()

    def test_cache_path(self, temp_data_root):
        """Test global cache path."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        cache_dir = paths.cache_path()
        assert cache_dir == temp_data_root / ".cache"
        assert cache_dir.exists()

    def test_separation_manifest_path(self, temp_data_root):
        """Test separation manifest path."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        manifest = paths.separation_manifest_path()
        assert manifest == temp_data_root / "test-db" / "separated" / "separation_manifest.json"
        assert manifest.parent.exists()

    def test_create_structure(self, temp_data_root):
        """Test creating complete folder structure."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")
        paths.create_structure()

        # Check all main categories exist
        assert (temp_data_root / "test-db" / "raw").exists()
        assert (temp_data_root / "test-db" / "separated").exists()
        assert (temp_data_root / "test-db" / "embeddings").exists()
        assert (temp_data_root / "test-db" / "graph").exists()
        assert (temp_data_root / "test-db" / "metadata").exists()

        # Check separated object type folders
        for obj_type in ["tables", "views", "stored_procedures", "functions", "schemas", "indexes", "triggers", "unknown"]:
            assert (temp_data_root / "test-db" / "separated" / obj_type).exists()

    def test_exists(self, temp_data_root):
        """Test database directory existence check."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        assert not paths.exists()  # Doesn't exist yet

        paths.create_structure()

        assert paths.exists()  # Now exists

    def test_get_path_manager_convenience_function(self, temp_data_root):
        """Test the convenience function."""
        paths = get_path_manager(database_name="test-db", data_root=temp_data_root)

        assert isinstance(paths, DataPathManager)
        assert paths.database_name == "test-db"
        assert paths.data_root == temp_data_root

    def test_multiple_databases(self, temp_data_root):
        """Test managing multiple databases."""
        db1 = DataPathManager(data_root=temp_data_root, database_name="database1")
        db2 = DataPathManager(data_root=temp_data_root, database_name="database2")

        db1.create_structure()
        db2.create_structure()

        assert (temp_data_root / "database1").exists()
        assert (temp_data_root / "database2").exists()
        assert (temp_data_root / "database1" / "raw").exists()
        assert (temp_data_root / "database2" / "raw").exists()

    def test_no_create_option(self, temp_data_root):
        """Test paths without automatic directory creation."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        raw_file = paths.raw_path("schema.sql", create_dir=False)
        assert raw_file == temp_data_root / "test-db" / "raw" / "schema.sql"
        assert not raw_file.parent.exists()  # Should NOT be created

    def test_repr_and_str(self, temp_data_root):
        """Test string representations."""
        paths = DataPathManager(data_root=temp_data_root, database_name="test-db")

        repr_str = repr(paths)
        assert "DataPathManager" in repr_str
        assert "test-db" in repr_str

        str_str = str(paths)
        assert "test-db" in str_str


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def temp_data_root(self):
        """Create a temporary data directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_complete_workflow(self, temp_data_root):
        """Test a complete workflow using DataPathManager."""
        import json

        # Detect database name from file
        db_name = detect_database_name("AdventureWorksLT-All.sql")
        assert db_name == "adventureworkslt"

        # Create path manager
        paths = DataPathManager(data_root=temp_data_root, database_name=db_name)
        paths.create_structure()

        # Simulate saving raw file
        raw_file = paths.raw_path("AdventureWorksLT-All.sql")
        raw_file.write_text("CREATE TABLE test (id INT);")
        assert raw_file.exists()

        # Simulate saving separated objects
        table_file = paths.separated_path("tables", "test.sql")
        table_file.write_text("CREATE TABLE test (id INT);")
        assert table_file.exists()

        # Simulate saving embeddings
        emb_file = paths.embeddings_path("sql_embeddings.json")
        embeddings = {"test": [0.1, 0.2, 0.3]}
        emb_file.write_text(json.dumps(embeddings))
        assert emb_file.exists()

        # Simulate saving graph export
        graph_file = paths.graph_path("graph_export.json")
        graph_data = {"nodes": [], "edges": []}
        graph_file.write_text(json.dumps(graph_data))
        assert graph_file.exists()

        # Simulate saving metadata
        log_file = paths.metadata_path("failed_ingestion.jsonl")
        log_file.write_text('{"error": "test"}\n')
        assert log_file.exists()

        # Verify structure
        assert len(list(paths.database_dir.rglob("*"))) > 10  # Many files/folders created


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
