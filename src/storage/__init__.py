"""
Storage module for metadata management.

Provides DuckDB-based storage for projects, repositories, links,
and Parquet archiving utilities.
"""

from .duckdb_client import DuckDBClient, get_duckdb_client
from .metadata_store import ProjectStore, RepositoryStore, LinkStore

__all__ = [
    "DuckDBClient",
    "get_duckdb_client",
    "ProjectStore",
    "RepositoryStore",
    "LinkStore",
]
