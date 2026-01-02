"""
Data path management utilities for hierarchical database folder structure.

This module provides utilities for constructing paths to data files organized
by database name and category (raw, separated, embeddings, graph, metadata).

Structure:
    data/
    └── {database-name}/
        ├── raw/
        ├── separated/
        ├── embeddings/
        ├── graph/
        └── metadata/
"""

import re
from pathlib import Path
from typing import Literal, Optional

# Type alias for data categories
DataCategory = Literal["raw", "separated", "embeddings", "graph", "metadata"]

# Valid SQL object types for separated folder
SQLObjectType = Literal[
    "tables",
    "views",
    "stored_procedures",
    "functions",
    "schemas",
    "indexes",
    "triggers",
    "unknown",
]


def normalize_database_name(name: str) -> str:
    """
    Normalize a database name to kebab-case.

    Converts to lowercase and replaces any sequence of non-alphanumeric
    characters with a single hyphen. Removes leading/trailing hyphens.

    Examples:
        >>> normalize_database_name("AdventureWorksLT-All")
        'adventureworks-lt-all'
        >>> normalize_database_name("sample_financial_schema")
        'sample-financial-schema'
        >>> normalize_database_name("MyDatabase.sql")
        'my-database-sql'
        >>> normalize_database_name("Test DB 123")
        'test-db-123'

    Args:
        name: The database name to normalize

    Returns:
        Normalized database name in kebab-case
    """
    # Convert to lowercase
    normalized = name.lower()

    # Replace sequences of non-alphanumeric characters with single hyphen
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)

    # Remove leading/trailing hyphens
    normalized = normalized.strip("-")

    return normalized


def detect_database_name(
    file_path: str | Path, explicit_name: Optional[str] = None
) -> str:
    """
    Detect database name from file path or use explicit name.

    Priority order:
    1. Explicit database name parameter
    2. Extract from filename (before first hyphen or underscore)
    3. Use parent directory name
    4. Default to "default"

    Examples:
        >>> detect_database_name("AdventureWorksLT-All.sql")
        'adventureworks-lt'
        >>> detect_database_name("schema.sql", explicit_name="MyDB")
        'my-db'
        >>> detect_database_name("/data/northwind/raw/schema.sql")
        'northwind'

    Args:
        file_path: Path to the file
        explicit_name: Explicitly provided database name (highest priority)

    Returns:
        Detected and normalized database name
    """
    if explicit_name:
        return normalize_database_name(explicit_name)

    path = Path(file_path)

    # Try extracting from filename (before first separator)
    filename = path.stem  # Remove extension

    # Check for hyphen separator (e.g., "AdventureWorksLT-All" -> "AdventureWorksLT")
    if "-" in filename:
        db_name = filename.split("-")[0]
        return normalize_database_name(db_name)

    # Check for underscore separator (e.g., "sample_financial_schema" -> "sample")
    if "_" in filename:
        db_name = filename.split("_")[0]
        return normalize_database_name(db_name)

    # Try using parent directory name if path has multiple parts
    if len(path.parts) > 1:
        parent = path.parent.name
        if parent and parent != "." and parent != "data":
            return normalize_database_name(parent)

    # Default fallback
    return "default"


class DataPathManager:
    """
    Manages file paths for hierarchical database folder structure.

    Provides methods to construct paths for different data categories
    and automatically creates directories as needed.

    Example:
        >>> paths = DataPathManager(data_root="./data", database_name="AdventureWorksLT")
        >>> paths.database_name
        'adventureworks-lt'
        >>> paths.embeddings_path("sql_embeddings.json")
        PosixPath('data/adventureworks-lt/embeddings/sql_embeddings.json')
        >>> paths.separated_path("tables")
        PosixPath('data/adventureworks-lt/separated/tables')
    """

    def __init__(self, data_root: str | Path, database_name: str):
        """
        Initialize the DataPathManager.

        Args:
            data_root: Root directory for all data (e.g., "./data")
            database_name: Name of the database (will be normalized)
        """
        self.data_root = Path(data_root)
        self.database_name = normalize_database_name(database_name)
        self.database_dir = self.data_root / self.database_name

    def get_category_path(self, category: DataCategory, create: bool = True) -> Path:
        """
        Get path for a specific category folder.

        Args:
            category: The data category (raw, separated, embeddings, graph, metadata)
            create: Whether to create the directory if it doesn't exist (default: True)

        Returns:
            Path to the category folder
        """
        path = self.database_dir / category
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def get_file_path(
        self, category: DataCategory, filename: str, create_dir: bool = True
    ) -> Path:
        """
        Get full path for a specific file within a category.

        Args:
            category: The data category
            filename: Name of the file
            create_dir: Whether to create the parent directory (default: True)

        Returns:
            Full path to the file
        """
        return self.get_category_path(category, create=create_dir) / filename

    # Convenience methods for specific categories

    def raw_path(self, filename: str, create_dir: bool = True) -> Path:
        """
        Get path for a raw SQL file.

        Args:
            filename: Name of the raw file
            create_dir: Whether to create the directory

        Returns:
            Path to the raw file
        """
        return self.get_file_path("raw", filename, create_dir=create_dir)

    def separated_path(
        self,
        object_type: SQLObjectType,
        filename: Optional[str] = None,
        create_dir: bool = True,
    ) -> Path:
        """
        Get path for separated SQL objects.

        Args:
            object_type: Type of SQL object (tables, views, procedures, etc.)
            filename: Optional filename within the object type folder
            create_dir: Whether to create the directory

        Returns:
            Path to the object type folder or specific file
        """
        sep_dir = self.get_category_path("separated", create=create_dir) / object_type
        if create_dir:
            sep_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            return sep_dir / filename
        return sep_dir

    def separation_manifest_path(self, create_dir: bool = True) -> Path:
        """
        Get path to the separation manifest file.

        Args:
            create_dir: Whether to create the directory

        Returns:
            Path to separation_manifest.json
        """
        sep_dir = self.get_category_path("separated", create=create_dir)
        return sep_dir / "separation_manifest.json"

    def embeddings_path(self, filename: str, create_dir: bool = True) -> Path:
        """
        Get path for an embeddings file.

        Args:
            filename: Name of the embeddings file
            create_dir: Whether to create the directory

        Returns:
            Path to the embeddings file
        """
        return self.get_file_path("embeddings", filename, create_dir=create_dir)

    def graph_path(self, filename: str, create_dir: bool = True) -> Path:
        """
        Get path for a graph export file.

        Args:
            filename: Name of the graph file
            create_dir: Whether to create the directory

        Returns:
            Path to the graph file
        """
        return self.get_file_path("graph", filename, create_dir=create_dir)

    def metadata_path(self, filename: str, create_dir: bool = True) -> Path:
        """
        Get path for a metadata file.

        Args:
            filename: Name of the metadata file
            create_dir: Whether to create the directory

        Returns:
            Path to the metadata file
        """
        return self.get_file_path("metadata", filename, create_dir=create_dir)

    def cache_path(self) -> Path:
        """
        Get path to the global cache directory.

        Note: Cache is global across all databases, not database-specific.

        Returns:
            Path to the .cache directory
        """
        cache_dir = self.data_root / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def exists(self) -> bool:
        """
        Check if the database directory exists.

        Returns:
            True if the database directory exists
        """
        return self.database_dir.exists()

    def create_structure(self) -> None:
        """
        Create the complete folder structure for this database.

        Creates all standard category folders:
        - raw/
        - separated/ (with all object type subfolders)
        - embeddings/
        - graph/
        - metadata/
        """
        # Create main category folders
        for category in ["raw", "separated", "embeddings", "graph", "metadata"]:
            self.get_category_path(category, create=True)

        # Create separated object type subfolders
        for object_type in [
            "tables",
            "views",
            "stored_procedures",
            "functions",
            "schemas",
            "indexes",
            "triggers",
            "unknown",
        ]:
            self.separated_path(object_type, create_dir=True)

    def __repr__(self) -> str:
        """String representation of the DataPathManager."""
        return f"DataPathManager(data_root='{self.data_root}', database_name='{self.database_name}')"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"DataPathManager for '{self.database_name}' at {self.database_dir}"


# Convenience function for quick path manager creation
def get_path_manager(
    database_name: str, data_root: str | Path = "./data"
) -> DataPathManager:
    """
    Create a DataPathManager instance with default data root.

    Args:
        database_name: Name of the database
        data_root: Root directory for data (default: "./data")

    Returns:
        Configured DataPathManager instance
    """
    return DataPathManager(data_root=data_root, database_name=database_name)
