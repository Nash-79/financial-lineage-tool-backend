"""
DuckDB client for metadata storage.

Provides persistent or in-memory storage for projects, repositories, and links.
Supports DuckDB SQL dialect features like QUALIFY, LIST aggregation, and JSON operators.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

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

        # Connect to database with retry mechanism
        import time
        max_retries = 5
        retry_delay = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                self.conn = duckdb.connect(self.db_path)
                break
            except (duckdb.Error, OSError) as e:
                if attempt == max_retries:
                    logger.error(f"Failed to connect to DuckDB after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"DuckDB connection attempt {attempt} failed ({e}). Retrying in {retry_delay}s...")
                time.sleep(retry_delay)

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
        target_version = 4

        # Migration status banner
        logger.info("=" * 70)
        logger.info("DATABASE SCHEMA MIGRATION CHECK")
        logger.info(f"Current version: {current_version}")
        logger.info(f"Target version: {target_version}")
        if current_version < target_version:
            logger.info(f"Migrations to apply: {target_version - current_version}")
        else:
            logger.info("Schema is up-to-date")
        logger.info("=" * 70)

        if current_version == 0:
            # Initial schema creation
            self._create_initial_schema()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (1)")
            logger.info("✓ Migration 0 → 1 completed successfully (initial schema)")
            current_version = 1

        if current_version == 1:
            # V2: Add project context support
            self._migrate_to_v2()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (2)")
            logger.info("✓ Migration 1 → 2 completed successfully (project context)")
            current_version = 2

        if current_version == 2:
            # V3: Add runs and files tables for artifact management
            self._migrate_to_v3()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (3)")
            logger.info("✓ Migration 2 → 3 completed successfully (artifact management)")
            current_version = 3

        if current_version == 3:
            # V4: Add upload_settings table for persistent configuration
            self._migrate_to_v4()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (4)")
            logger.info("✓ Migration 3 → 4 completed successfully (upload settings persistence)")
            current_version = 4

        # Completion banner
        logger.info("=" * 70)
        logger.info("DATABASE SCHEMA MIGRATION COMPLETE")
        logger.info(f"Final version: {current_version}")
        logger.info("=" * 70)

    def _migrate_to_v2(self) -> None:
        """
        Migrate schema from v1 to v2: Add project context support.

        WHAT: Add context storage columns to projects table
        WHY: Enable storing structured context and uploaded context files
        WHEN: 2026-01-02 (add-user-prompt-context OpenSpec change)

        SCHEMA CHANGES:
        - ALTER TABLE projects ADD COLUMN context JSON
          Purpose: Store structured context data (JSON format)
        - ALTER TABLE projects ADD COLUMN context_file_path VARCHAR
          Purpose: Path to uploaded context file

        DATA MIGRATION: None (new columns, no existing data)
        ROLLBACK: Not needed (additive change only)
        RISK LEVEL: Low (adds columns with no constraints)
        AFFECTED FEATURES: Project context API endpoints
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Add context column (JSON for structured context)
        self.conn.execute("""
            ALTER TABLE projects
            ADD COLUMN IF NOT EXISTS context JSON
        """)

        # Add context file path column
        self.conn.execute("""
            ALTER TABLE projects
            ADD COLUMN IF NOT EXISTS context_file_path VARCHAR
        """)

        logger.info("Added context and context_file_path columns to projects table")

    def _migrate_to_v3(self) -> None:
        """
        Migrate schema from v2 to v3: Add artifact management system.

        WHAT: Create runs and files tables for hierarchical data organization
        WHY: Track ingestion runs and file versions with content hashing
        WHEN: 2026-01-02 (structure-data-outputs OpenSpec change)

        SCHEMA CHANGES:
        - CREATE TABLE runs
          Purpose: Track ingestion runs with timestamp/sequence/status
        - CREATE TABLE files
          Purpose: Track file versions with SHA256 hashing
        - CREATE INDEX idx_runs_project_timestamp
        - CREATE INDEX idx_files_project_filename
        - CREATE INDEX idx_files_hash
        - CREATE INDEX idx_files_project_hash
        - CREATE INDEX idx_files_run
        - CREATE MACRO get_next_sequence(proj_id, ts)
          Purpose: Get next sequence number for concurrent runs
        - CREATE MACRO find_duplicate_file(proj_id, fname, fhash)
          Purpose: Find duplicate files by content hash
        - CREATE MACRO find_previous_file_version(proj_id, fname)
          Purpose: Find previous version of a file for superseding

        DATA MIGRATION: None (new tables)
        ROLLBACK: Not needed (additive change only)
        RISK LEVEL: Medium (complex schema with indexes and macros)
        AFFECTED FEATURES: File upload, artifact management, deduplication
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Create runs table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                timestamp VARCHAR NOT NULL,
                sequence INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT current_timestamp,
                completed_at TIMESTAMP,
                error_message VARCHAR,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        # Create files table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL,
                filename VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                file_hash VARCHAR(64) NOT NULL,
                file_size_bytes BIGINT NOT NULL,
                is_superseded BOOLEAN DEFAULT false,
                superseded_by VARCHAR,
                created_at TIMESTAMP DEFAULT current_timestamp,
                processed_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (run_id) REFERENCES runs(id)
            )
        """)

        # Create indexes for performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_project_timestamp ON runs(project_id, timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_project_filename ON files(project_id, filename)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_project_hash ON files(project_id, filename, file_hash)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_run ON files(run_id)")

        # Create stored procedures and functions for metadata operations
        # Note: DuckDB uses CREATE OR REPLACE MACRO for functions
        
        # Function: Get next sequence number for a run
        self.conn.execute("""
            CREATE OR REPLACE MACRO get_next_sequence(proj_id, ts) AS (
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM runs
                WHERE project_id = proj_id AND timestamp = ts
            )
        """)

        # Function: Find duplicate file by hash
        self.conn.execute("""
            CREATE OR REPLACE MACRO find_duplicate_file(proj_id, fname, fhash) AS TABLE (
                SELECT id, run_id, file_path
                FROM files
                WHERE project_id = proj_id 
                  AND filename = fname 
                  AND file_hash = fhash 
                  AND is_superseded = false
                LIMIT 1
            )
        """)

        # Function: Find previous version of a file (same filename, different hash)
        self.conn.execute("""
            CREATE OR REPLACE MACRO find_previous_file_version(proj_id, fname) AS TABLE (
                SELECT id, run_id, file_hash
                FROM files
                WHERE project_id = proj_id 
                  AND filename = fname 
                  AND is_superseded = false
                LIMIT 1
            )
        """)

        logger.info("Created runs and files tables with indexes and stored procedures")

    def _migrate_to_v4(self) -> None:
        """
        Migrate schema from v3 to v4: Add persistent upload settings.

        WHAT: Create upload_settings table for configuration persistence
        WHY: Upload settings should survive server restarts
        WHEN: 2026-01-03 (persist-upload-settings OpenSpec change)

        SCHEMA CHANGES:
        - CREATE TABLE upload_settings
          - id: PRIMARY KEY (single row: 'default')
          - allowed_extensions: VARCHAR (JSON array stored as string)
          - max_file_size_mb: INTEGER (file size limit)
          - updated_at: TIMESTAMP (last modification time)
          - updated_by: VARCHAR (who made the change: api|system)

        DATA MIGRATION: None (new table, populated on first use)
        ROLLBACK: Not needed (additive change only)
        RISK LEVEL: Low (simple single-row table)
        AFFECTED FEATURES: File upload configuration API
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Create upload_settings table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS upload_settings (
                id VARCHAR PRIMARY KEY DEFAULT 'default',
                allowed_extensions VARCHAR NOT NULL,
                max_file_size_mb INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR
            )
        """)

        logger.info("Created upload_settings table for persistent configuration")

    def get_migration_status(self) -> Dict[str, Any]:
        """
        Get current database schema migration status.

        Returns:
            Dictionary containing:
            - current_version: Latest applied schema version
            - latest_version: Target schema version
            - total_migrations: Total number of migrations applied
            - migrations: List of applied migrations with timestamps
            - is_current: Whether database is at latest version

        Example:
            {
                "current_version": 4,
                "latest_version": 4,
                "is_current": True,
                "total_migrations": 4,
                "migrations": [
                    {"version": 1, "applied_at": "2026-01-03T12:00:00"},
                    {"version": 2, "applied_at": "2026-01-03T12:00:01"},
                    ...
                ]
            }
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        result = self.conn.execute(
            "SELECT version, applied_at FROM schema_version ORDER BY version"
        ).fetchall()

        current_version = result[-1][0] if result else 0
        latest_version = 4  # Update when new migrations added

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "is_current": current_version == latest_version,
            "total_migrations": len(result),
            "migrations": [
                {
                    "version": r[0],
                    "applied_at": r[1].isoformat() if r[1] else None
                }
                for r in result
            ]
        }


    def _create_initial_schema(self) -> None:
        """
        Create initial database schema (v1).

        WHAT: Create core tables for project and repository management
        WHY: Foundation for tracking projects, repositories, and their relationships
        WHEN: Initial implementation

        SCHEMA CHANGES:
        - CREATE TABLE projects
          Purpose: Store project metadata (id, name, description, created_at)
        - CREATE TABLE repositories
          Purpose: Store repository metadata (id, project_id, name, url, branch, created_at)
        - CREATE TABLE links
          Purpose: Store cross-repository links (id, project_id, source_repo, target_repo, etc.)
        - CREATE TABLE schema_version
          Purpose: Track applied migrations

        DATA MIGRATION: N/A (initial creation)
        ROLLBACK: N/A (initial creation)
        RISK LEVEL: None (initial creation)
        AFFECTED FEATURES: Core project management
        """
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
