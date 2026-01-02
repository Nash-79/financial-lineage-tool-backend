"""
DuckDB client for metadata storage.

Provides persistent or in-memory storage for projects, repositories, and links.
Supports DuckDB SQL dialect features like QUALIFY, LIST aggregation, and JSON operators.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import duckdb

logger = logging.getLogger(__name__)


class DuckDBClient:
    """
    DuckDB client for metadata storage.

    Supports:
    - Persistent mode: data/metadata.duckdb (local hosting)
    - In-memory mode: :memory: (cloud/serverless hosting)

    Thread safety is handled via asyncio.Lock for write operations.
    DuckDB supports concurrent reads natively (MVCC).
    """

    def __init__(self, db_path: str = "data/metadata.duckdb"):
        """
        Initialize DuckDB client.

        Args:
            db_path: Path to DuckDB database file, or ":memory:" for in-memory.
        """
        self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        self._write_lock = asyncio.Lock()
        self._initialized = False

    def initialize(self) -> None:
        """
        Initialize DuckDB connection and create schema.

        Creates the database file if it doesn't exist (for persistent mode).
        Creates all required tables, indexes, and constraints.
        """
        if self._initialized:
            logger.warning("DuckDB already initialized")
            return

        # Create parent directory for persistent databases
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initializing persistent DuckDB at: {self.db_path}")
        else:
            logger.info("Initializing in-memory DuckDB")

        # Connect to database
        self.conn = duckdb.connect(self.db_path)

        # Create schema
        self._create_schema()
        self._initialized = True
        logger.info("DuckDB initialization complete")

    def _create_schema(self) -> None:
        """Create database schema with tables, indexes, and constraints."""
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Schema version tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

        # Check current version
        result = self.conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = result[0] if result and result[0] else 0

        if current_version == 0:
            # Initial schema creation
            self._create_initial_schema()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (1)")
            logger.info("Created initial schema (version 1)")

    def _create_initial_schema(self) -> None:
        """Create initial database tables."""
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Projects table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                description VARCHAR,
                created_at TIMESTAMP DEFAULT current_timestamp,
                updated_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

        # Repositories table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                source_ref VARCHAR,
                file_count INTEGER DEFAULT 0,
                node_count INTEGER DEFAULT 0,
                last_synced TIMESTAMP,
                created_at TIMESTAMP DEFAULT current_timestamp,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        # Links table (relationships between repositories)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                source_repo_id VARCHAR NOT NULL,
                target_repo_id VARCHAR NOT NULL,
                link_type VARCHAR NOT NULL,
                description VARCHAR,
                confidence FLOAT,
                evidence JSON,
                created_at TIMESTAMP DEFAULT current_timestamp,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (source_repo_id) REFERENCES repositories(id),
                FOREIGN KEY (target_repo_id) REFERENCES repositories(id)
            )
        """)

        # System logs table for centralized logging
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                log_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT current_timestamp,
                level VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                message VARCHAR NOT NULL,
                context JSON
            )
        """)

        # Create indexes for common queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_repos_project ON repositories(project_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_links_project ON links(project_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_repo_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_repo_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)")

        logger.info("Created tables and indexes")

    async def execute_write(self, query: str, params: tuple = ()) -> Any:
        """
        Execute a write query with lock serialization.

        Uses asyncio.Lock to prevent concurrent writes which could cause
        DuckDB locking errors.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Query result
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        async with self._write_lock:
            try:
                return self.conn.execute(query, params)
            except duckdb.IOException as e:
                logger.error(f"DuckDB write error: {e}")
                raise

    def execute_read(self, query: str, params: tuple = ()) -> Any:
        """
        Execute a read query.

        DuckDB supports concurrent reads via MVCC, so no locking needed.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Query result
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        return self.conn.execute(query, params)

    def fetchall(self, query: str, params: tuple = ()) -> list[tuple]:
        """
        Execute query and fetch all results.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of result tuples
        """
        return self.execute_read(query, params).fetchall()

    def fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]:
        """
        Execute query and fetch one result.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Result tuple or None
        """
        return self.execute_read(query, params).fetchone()

    def close(self) -> None:
        """Close DuckDB connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self._initialized = False
            logger.info("DuckDB connection closed")

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized


# Global client instance
_duckdb_client: Optional[DuckDBClient] = None


def get_duckdb_client() -> DuckDBClient:
    """Get global DuckDB client instance."""
    global _duckdb_client
    if _duckdb_client is None:
        raise RuntimeError("DuckDB client not initialized. Call initialize_duckdb() first.")
    return _duckdb_client


def initialize_duckdb(db_path: str = "data/metadata.duckdb") -> DuckDBClient:
    """
    Initialize global DuckDB client.

    Args:
        db_path: Path to DuckDB database file, or ":memory:" for in-memory.

    Returns:
        Initialized DuckDBClient instance
    """
    global _duckdb_client
    if _duckdb_client is not None and _duckdb_client.is_initialized:
        logger.warning("DuckDB client already initialized")
        return _duckdb_client

    _duckdb_client = DuckDBClient(db_path)
    _duckdb_client.initialize()
    return _duckdb_client


def close_duckdb() -> None:
    """Close global DuckDB client."""
    global _duckdb_client
    if _duckdb_client is not None:
        _duckdb_client.close()
        _duckdb_client = None
