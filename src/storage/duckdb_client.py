"""
DuckDB client for metadata storage.

Provides persistent or in-memory storage for projects, repositories, and links.
Supports DuckDB SQL dialect features like QUALIFY, LIST aggregation, and JSON operators.

Phase 1 Integration: Optional connection pooling for better concurrency.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb
from src.storage.snapshot_manager import SnapshotManager

# Phase 1: Connection pool integration
try:
    from src.storage.duckdb_connection_pool import DuckDBConnectionPool, PooledConnection
    CONNECTION_POOL_AVAILABLE = True
except ImportError:
    CONNECTION_POOL_AVAILABLE = False
    logger.warning("Connection pool module not available, using singleton mode only")

# Phase 2: Transaction support
try:
    from src.storage.duckdb_transactions import DuckDBTransaction, TransactionManager
    TRANSACTIONS_AVAILABLE = True
except ImportError:
    TRANSACTIONS_AVAILABLE = False
    logger.warning("Transaction module not available")

# Phase 3: Query caching
try:
    from src.storage.query_cache import QueryCache
    QUERY_CACHE_AVAILABLE = True
except ImportError:
    QUERY_CACHE_AVAILABLE = False
    logger.warning("Query cache module not available")

# Phase 4: Error handling
try:
    from src.storage.database_exceptions import (
        DatabaseException,
        ConnectionException,
        QueryException,
        TransactionException,
    )
    DATABASE_EXCEPTIONS_AVAILABLE = True
except ImportError:
    DATABASE_EXCEPTIONS_AVAILABLE = False
    logger.warning("Database exceptions module not available")

logger = logging.getLogger(__name__)



class DuckDBClient:
    """
    DuckDB client for metadata storage.

    Supports:
    - Persistent mode: data/metadata.duckdb (local hosting)
    - In-memory mode: :memory: (cloud/serverless hosting)
    - Connection pooling: Optional for better concurrency (Phase 1)

    Thread safety is handled via asyncio.Lock for write operations.
    DuckDB supports concurrent reads natively (MVCC).
    """

    def __init__(
        self,
        db_path: str = "data/metadata.duckdb",
        enable_snapshots: bool = True,
        snapshot_keep_count: int = 5,
        snapshots_dir: str = "data/snapshots",
        # Phase 1: Connection pool parameters
        enable_connection_pool: bool = False,
        pool_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize DuckDB client.

        Args:
            db_path: Path to DuckDB database file, or ":memory:" for in-memory.
            enable_snapshots: Enable automatic snapshots for in-memory mode (default: True)
            snapshot_keep_count: Number of snapshots to retain
            snapshots_dir: Directory for snapshot storage
            enable_connection_pool: Enable connection pooling (Phase 1, default: False)
            pool_config: Connection pool configuration (max_connections, min_connections, etc.)
        """
        self.db_path = db_path
        self._is_memory_mode = db_path == ":memory:"
        self._initialized = False
        
        # Phase 1: Connection pool support
        self._enable_pool = enable_connection_pool and CONNECTION_POOL_AVAILABLE
        self._pool: Optional[DuckDBConnectionPool] = None
        
        if self._enable_pool:
            # Initialize connection pool
            pool_config = pool_config or {}
            self._pool = DuckDBConnectionPool(
                db_path=db_path,
                **pool_config
            )
            logger.info(f"Connection pool enabled for {db_path}")
            # No direct connection in pool mode
            self.conn: Optional[duckdb.DuckDBPyConnection] = None
        else:
            # Traditional singleton connection
            self.conn: Optional[duckdb.DuckDBPyConnection] = None
            self._write_lock = asyncio.Lock()
        
        # Initialize snapshot manager for in-memory mode (singleton only)
        self.snapshot_manager: Optional[SnapshotManager] = None
        self._pending_snapshot = False  # Track if snapshot is needed
        if self._is_memory_mode and enable_snapshots and not self._enable_pool:
            self.snapshot_manager = SnapshotManager(
                snapshots_dir=snapshots_dir,
                keep_count=snapshot_keep_count,
            )
            logger.info("Snapshot manager enabled for in-memory mode")


    async def save_chat_artifact(
        self,
        session_id: str,
        message_id: str,
        artifact_type: str,
        content: Dict[str, Any],
    ) -> bool:
        """
        Save a chat artifact (e.g., lineage graph) for a specific message.

        Args:
            session_id: Chat session identifier
            message_id: Message identifier within session
            artifact_type: Type of artifact (e.g., 'graph')
            content: JSON content of the artifact

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.conn:
            logger.error("DuckDB connection not initialized")
            return False

        try:
            import json

            content_json = json.dumps(content)
            async with self._write_lock:
                # Upsert artifact
                self.conn.execute(
                    """
                    INSERT INTO chat_artifacts (session_id, message_id, artifact_type, artifact_data)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (session_id, message_id, artifact_type) 
                    DO UPDATE SET artifact_data = excluded.artifact_data, created_at = CURRENT_TIMESTAMP
                """,
                    [session_id, message_id, artifact_type, content_json],
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save chat artifact: {e}")
            return False

    async def get_chat_artifact(
        self,
        session_id: str,
        message_id: str,
        artifact_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chat artifact by its identifiers.

        Args:
            session_id: Chat session identifier
            message_id: Message identifier within session
            artifact_type: Type of artifact (e.g., 'graph')

        Returns:
            Dictionary payload of the artifact if found, None otherwise
        """
        if not self.conn:
            logger.error("DuckDB connection not initialized")
            return None

        try:
            import json

            result = self.conn.execute(
                """
                SELECT artifact_data 
                FROM chat_artifacts 
                WHERE session_id = ? AND message_id = ? AND artifact_type = ?
            """,
                [session_id, message_id, artifact_type],
            ).fetchone()

            if result and result[0]:
                return json.loads(result[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get chat artifact: {e}")
            return None

    def initialize(self) -> None:
        """
        Initialize DuckDB connection and create schema.

        For persistent mode: Creates database file if it doesn't exist.
        For in-memory mode: Loads latest snapshot if available.
        For connection pool mode: Marks as initialized (pool initializes on first use).
        Creates all required tables, indexes, and constraints.
        """
        if self._initialized:
            logger.warning("DuckDB already initialized")
            return
        
        # Phase 1: Connection pool mode - defer initialization to first use
        if self._enable_pool and self._pool:
            logger.info("Connection pool mode enabled - pool will initialize on first use")
            self._initialized = True
            return

        # Create parent directory for persistent databases
        if not self._is_memory_mode:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initializing persistent DuckDB at: {self.db_path}")
        else:
            logger.info("Initializing in-memory DuckDB")

        # Connect to database
        if not self._is_memory_mode:
            # Persistent mode: Connect with retry mechanism for file locking
            import time

            max_retries = 5
            retry_delay = 1.0

            for attempt in range(1, max_retries + 1):
                try:
                    self.conn = duckdb.connect(self.db_path)
                    break
                except (duckdb.Error, OSError) as e:
                    if attempt == max_retries:
                        logger.error(
                            f"Failed to connect to DuckDB after {max_retries} attempts: {e}"
                        )
                        raise
                    logger.warning(
                        f"DuckDB connection attempt {attempt} failed ({e}). Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
        else:
            # In-memory mode: Connect immediately (no file locking issues)
            self.conn = duckdb.connect(":memory:")

        # Load latest snapshot for in-memory mode before applying migrations
        if self._is_memory_mode and self.snapshot_manager:
            latest_snapshot = self.snapshot_manager.get_latest_snapshot()
            if latest_snapshot:
                try:
                    logger.info(
                        f"Loading latest snapshot: {os.path.basename(latest_snapshot)}"
                    )
                    self.snapshot_manager.load_snapshot(self.conn, latest_snapshot)
                    logger.info("Snapshot loaded successfully")
                except Exception as e:
                    logger.warning(
                        f"Failed to load snapshot, starting with empty database: {e}"
                    )
            else:
                logger.info("No snapshot found, starting with empty database")

        # Create schema / apply migrations
        self._create_schema()

        self._initialized = True
        logger.info("DuckDB initialization complete")

    def _create_schema(self) -> None:
        """Create database schema with tables, indexes, and constraints."""
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Schema version tracking
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT current_timestamp
            )
        """
        )

        # Check current version
        result = self.conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = result[0] if result and result[0] else 0
        target_version = 8

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
            logger.info(
                "✓ Migration 2 → 3 completed successfully (artifact management)"
            )
            current_version = 3

        if current_version == 3:
            # V4: Add upload_settings table for persistent configuration
            self._migrate_to_v4()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (4)")
            logger.info(
                "✓ Migration 3 → 4 completed successfully (upload settings persistence)"
            )
            current_version = 4

        if current_version == 4:
            # V5: Add file metadata columns for frontend wiring
            self._migrate_to_v5()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (5)")
            logger.info(
                "Migration 4 -> 5 completed successfully (file metadata columns)"
            )
            current_version = 5

        if current_version == 5:
            # V6: Rebuild files table without primary key + add project links
            self._migrate_to_v6()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (6)")
            logger.info(
                "Migration 5 -> 6 completed successfully (files table rebuild + project links)"
            )
            current_version = 6

        if current_version == 6:
            # V7: Add chat_artifacts table for message-scoped graph data persistence
            self._migrate_to_v7()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (7)")
            logger.info(
                "Migration 6 -> 7 completed successfully (chat artifacts table)"
            )
            current_version = 7

        if current_version == 7:
            # V8: Add model_configs table for unified model configuration
            self._migrate_to_v8()
            self.conn.execute("INSERT INTO schema_version (version) VALUES (8)")
            logger.info(
                "Migration 7 -> 8 completed successfully (model configs table)"
            )
            current_version = 8

        self._ensure_file_macros()

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
        self.conn.execute(
            """
            ALTER TABLE projects
            ADD COLUMN IF NOT EXISTS context JSON
        """
        )

        # Add context file path column
        self.conn.execute(
            """
            ALTER TABLE projects
            ADD COLUMN IF NOT EXISTS context_file_path VARCHAR
        """
        )

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
        - CREATE MACRO find_duplicate_file(proj_id, repo_id, rel_path, fhash)
          Purpose: Find duplicate files by content hash
        - CREATE MACRO find_previous_file_version(proj_id, repo_id, rel_path)
          Purpose: Find previous version of a file for superseding

        DATA MIGRATION: None (new tables)
        ROLLBACK: Not needed (additive change only)
        RISK LEVEL: Medium (complex schema with indexes and macros)
        AFFECTED FEATURES: File upload, artifact management, deduplication
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Create runs table
        self.conn.execute(
            """
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
        """
        )

        # Create files table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id VARCHAR NOT NULL,
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
        """
        )

        # Create indexes for performance
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_project_timestamp ON runs(project_id, timestamp)"
        )
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_files_id ON files(id)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_project_filename ON files(project_id, filename)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_project_hash ON files(project_id, filename, file_hash)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_run ON files(run_id)")

        # Create stored procedures and functions for metadata operations
        # Note: DuckDB uses CREATE OR REPLACE MACRO for functions

        # Function: Get next sequence number for a run
        self.conn.execute(
            """
            CREATE OR REPLACE MACRO get_next_sequence(proj_id, ts) AS (
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM runs
                WHERE project_id = proj_id AND timestamp = ts
            )
        """
        )

        # Function: Find duplicate file by hash
        self.conn.execute(
            """
            CREATE OR REPLACE MACRO find_duplicate_file(proj_id, repo_id, rel_path, fhash) AS TABLE (
                SELECT id, run_id, file_path
                FROM files
                WHERE project_id = proj_id
                  AND filename = rel_path
                  AND file_hash = fhash
                  AND is_superseded = false
                LIMIT 1
            )
        """
        )

        # Function: Find previous version of a file (same filename, different hash)
        self.conn.execute(
            """
            CREATE OR REPLACE MACRO find_previous_file_version(proj_id, repo_id, rel_path) AS TABLE (
                SELECT id, run_id, file_hash
                FROM files
                WHERE project_id = proj_id
                  AND filename = rel_path
                  AND is_superseded = false
                LIMIT 1
            )
        """
        )

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
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_settings (
                id VARCHAR PRIMARY KEY DEFAULT 'default',
                allowed_extensions VARCHAR NOT NULL,
                max_file_size_mb INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR
            )
        """
        )

        logger.info("Created upload_settings table for persistent configuration")

    def _migrate_to_v5(self) -> None:
        """
        Migrate schema from v4 to v5: Add file metadata columns for frontend wiring.

        WHAT: Add relative_path, file_type, source, repository_id, status to files table
        WHY: Support file listing, filtering, and path preservation in UI
        WHEN: 2026-01-09 (align-frontend-backend-api OpenSpec change)

        SCHEMA CHANGES:
        - ALTER TABLE files ADD COLUMN relative_path
        - ALTER TABLE files ADD COLUMN file_type
        - ALTER TABLE files ADD COLUMN source
        - ALTER TABLE files ADD COLUMN repository_id
        - ALTER TABLE files ADD COLUMN status
        - CREATE INDEX idx_files_project_relative_path
        - CREATE INDEX idx_files_repository
        - CREATE INDEX idx_files_source
        - CREATE INDEX idx_files_status
        - CREATE OR REPLACE MACRO find_duplicate_file(...)
        - CREATE OR REPLACE MACRO find_previous_file_version(...)

        DATA MIGRATION: None (additive columns)
        ROLLBACK: Not needed (additive change only)
        RISK LEVEL: Low (additive columns, new indexes)
        AFFECTED FEATURES: File listing, ingestion metadata, UI wiring
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Drop dependent macros before altering table schema.
        self.conn.execute("DROP MACRO IF EXISTS find_duplicate_file")
        self.conn.execute("DROP MACRO IF EXISTS find_previous_file_version")

        self.conn.execute(
            """
            ALTER TABLE files
            ADD COLUMN IF NOT EXISTS relative_path VARCHAR
        """
        )
        self.conn.execute(
            """
            ALTER TABLE files
            ADD COLUMN IF NOT EXISTS file_type VARCHAR
        """
        )
        self.conn.execute(
            """
            ALTER TABLE files
            ADD COLUMN IF NOT EXISTS source VARCHAR
        """
        )
        self.conn.execute(
            """
            ALTER TABLE files
            ADD COLUMN IF NOT EXISTS repository_id VARCHAR
        """
        )
        self.conn.execute(
            """
            ALTER TABLE files
            ADD COLUMN IF NOT EXISTS status VARCHAR
        """
        )

        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_project_relative_path ON files(project_id, relative_path)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_repository ON files(repository_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_source ON files(source)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)"
        )

        self.conn.execute(
            """
            CREATE OR REPLACE MACRO find_duplicate_file(proj_id, repo_id, rel_path, fhash) AS TABLE (
                SELECT id, run_id, file_path
                FROM files
                WHERE project_id = proj_id
                  AND (repository_id = repo_id OR (repository_id IS NULL AND repo_id IS NULL))
                  AND COALESCE(relative_path, filename) = rel_path
                  AND file_hash = fhash
                  AND is_superseded = false
                LIMIT 1
            )
        """
        )

        self.conn.execute(
            """
            CREATE OR REPLACE MACRO find_previous_file_version(proj_id, repo_id, rel_path) AS TABLE (
                SELECT id, run_id, file_hash
                FROM files
                WHERE project_id = proj_id
                  AND (repository_id = repo_id OR (repository_id IS NULL AND repo_id IS NULL))
                  AND COALESCE(relative_path, filename) = rel_path
                  AND is_superseded = false
                LIMIT 1
            )
        """
        )

        logger.info("Added file metadata columns and updated file versioning macros")

    def _migrate_to_v6(self) -> None:
        """
        Migrate schema from v5 to v6: Rebuild files table without primary key and add project links.

        WHAT: Remove DuckDB primary key on files.id to avoid constraint update issues.
        WHY: DuckDB raises false constraint errors on UPDATE with PRIMARY KEY in some builds.
        WHEN: 2026-01-13 (enhance-zero-cost-hybrid-lineage updates)

        SCHEMA CHANGES:
        - Recreate files table without PRIMARY KEY (use UNIQUE index instead)
        - CREATE UNIQUE INDEX idx_files_id ON files(id)
        - CREATE TABLE project_links for cross-project relationships
        - CREATE INDEX idx_project_links_source/target

        DATA MIGRATION: Copy files data into rebuilt table
        ROLLBACK: Not supported (manual)
        RISK LEVEL: Medium (table rebuild)
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Drop macros that depend on files table before rebuilding.
        self.conn.execute("DROP MACRO IF EXISTS find_duplicate_file")
        self.conn.execute("DROP MACRO IF EXISTS find_previous_file_version")

        # Rebuild files table without primary key.
        self.conn.execute("DROP TABLE IF EXISTS files_new")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files_new (
                id VARCHAR NOT NULL,
                project_id VARCHAR NOT NULL,
                repository_id VARCHAR,
                run_id VARCHAR NOT NULL,
                filename VARCHAR NOT NULL,
                relative_path VARCHAR,
                file_type VARCHAR,
                source VARCHAR,
                status VARCHAR,
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
        """
        )

        self.conn.execute(
            """
            INSERT INTO files_new (
                id, project_id, repository_id, run_id, filename, relative_path,
                file_type, source, status, file_path, file_hash, file_size_bytes,
                is_superseded, superseded_by, created_at, processed_at
            )
            SELECT
                id, project_id, repository_id, run_id, filename, relative_path,
                file_type, source, status, file_path, file_hash, file_size_bytes,
                is_superseded, superseded_by, created_at, processed_at
            FROM files
        """
        )

        self.conn.execute("DROP TABLE files")
        self.conn.execute("ALTER TABLE files_new RENAME TO files")

        # Recreate indexes for files table.
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_files_id ON files(id)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_project_filename ON files(project_id, filename)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_project_hash ON files(project_id, filename, file_hash)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_run ON files(run_id)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_project_relative_path ON files(project_id, relative_path)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_repository ON files(repository_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_source ON files(source)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)"
        )

        # Create project_links table for cross-project links.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_links (
                id VARCHAR PRIMARY KEY,
                source_project_id VARCHAR NOT NULL,
                target_project_id VARCHAR NOT NULL,
                link_type VARCHAR NOT NULL,
                description VARCHAR,
                created_at TIMESTAMP DEFAULT current_timestamp,
                FOREIGN KEY (source_project_id) REFERENCES projects(id),
                FOREIGN KEY (target_project_id) REFERENCES projects(id)
            )
        """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_links_source ON project_links(source_project_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_links_target ON project_links(target_project_id)"
        )

        logger.info(
            "Rebuilt files table without primary key and created project_links table"
        )

    def _migrate_to_v7(self) -> None:
        """
        Migrate schema from v6 to v7: Add chat_artifacts table.

        WHAT: Create chat_artifacts table for message-scoped graph data persistence
        WHY: Allow users to retrieve answer-specific lineage graphs after conversation advances
        WHEN: 2026-01-14 (update-chat-models-and-lineage OpenSpec change)

        SCHEMA CHANGES:
        - CREATE TABLE chat_artifacts
          - session_id: TEXT NOT NULL (chat session identifier)
          - message_id: TEXT NOT NULL (message identifier within session)
          - artifact_type: TEXT NOT NULL (e.g., "graph" for lineage graphs)
          - artifact_data: JSON NOT NULL (the artifact payload)
          - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          - PRIMARY KEY (session_id, message_id, artifact_type)
        - CREATE INDEX idx_chat_artifacts_created_at (for cleanup queries)

        DATA MIGRATION: None (new table)
        ROLLBACK: DROP TABLE chat_artifacts
        RISK LEVEL: Low (additive change only)
        AFFECTED FEATURES: Chat artifact persistence and retrieval API
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_artifacts (
                session_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                artifact_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, message_id, artifact_type)
            )
        """
        )

        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_artifacts_created_at ON chat_artifacts(created_at)"
        )

        logger.info("Created chat_artifacts table with indexes")

    def _migrate_to_v8(self) -> None:
        """
        Migrate schema from v7 to v8: Add model_configs table.

        WHAT: Create model_configs table for unified model configuration system
        WHY: Enable centralized model assignment and fallback chains per usage type
        WHEN: 2026-01-18 (dockerize-frontend and model configuration fixes)

        SCHEMA CHANGES:
        - CREATE TABLE model_configs
          - id: VARCHAR PRIMARY KEY (UUID)
          - usage_type: VARCHAR NOT NULL (e.g., "chat_deep", "embedding")
          - priority: INTEGER NOT NULL (1=primary, 2=secondary, etc.)
          - model_id: VARCHAR NOT NULL (model identifier)
          - model_name: VARCHAR NOT NULL (human-readable name)
          - provider: VARCHAR NOT NULL (e.g., "openrouter", "ollama")
          - parameters: JSON (optional model-specific parameters)
          - enabled: BOOLEAN DEFAULT TRUE
          - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          - updated_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          - UNIQUE (usage_type, priority)
        - CREATE INDEX idx_model_configs_usage_type
        - CREATE INDEX idx_model_configs_enabled

        DATA MIGRATION: None (new table, auto-seeded on first use)
        ROLLBACK: DROP TABLE model_configs
        RISK LEVEL: Low (additive change only)
        AFFECTED FEATURES: Model configuration API, chat services
        """
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        # Create model_configs table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_configs (
                id VARCHAR PRIMARY KEY,
                usage_type VARCHAR NOT NULL,
                priority INTEGER NOT NULL,
                model_id VARCHAR NOT NULL,
                model_name VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                parameters JSON,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (usage_type, priority)
            )
        """
        )

        # Create indexes for performance
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_configs_usage_type ON model_configs(usage_type)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_configs_enabled ON model_configs(enabled)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_configs_usage_priority ON model_configs(usage_type, priority)"
        )

        logger.info("Created model_configs table with indexes")


    def _ensure_file_macros(self) -> None:
        """Ensure file deduplication macros use repository-aware signatures."""
        if not self.conn:
            raise RuntimeError("DuckDB connection not initialized")

        try:
            self.conn.execute("DROP MACRO IF EXISTS find_duplicate_file")
            self.conn.execute("DROP MACRO IF EXISTS find_previous_file_version")
            self.conn.execute(
                """
                CREATE OR REPLACE MACRO find_duplicate_file(proj_id, repo_id, rel_path, fhash) AS TABLE (
                    SELECT id, run_id, file_path
                    FROM files
                    WHERE project_id = proj_id
                      AND (repository_id = repo_id OR (repository_id IS NULL AND repo_id IS NULL))
                      AND COALESCE(relative_path, filename) = rel_path
                      AND file_hash = fhash
                      AND is_superseded = false
                    LIMIT 1
                )
            """
            )

            self.conn.execute(
                """
                CREATE OR REPLACE MACRO find_previous_file_version(proj_id, repo_id, rel_path) AS TABLE (
                    SELECT id, run_id, file_hash
                    FROM files
                    WHERE project_id = proj_id
                      AND (repository_id = repo_id OR (repository_id IS NULL AND repo_id IS NULL))
                      AND COALESCE(relative_path, filename) = rel_path
                      AND is_superseded = false
                    LIMIT 1
                )
            """
            )
        except Exception as exc:
            logger.warning("Failed to ensure file macros: %s", exc)

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
                "current_version": 5,
                "latest_version": 5,
                "is_current": True,
                "total_migrations": 5,
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
        latest_version = 7  # Update when new migrations added

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "is_current": current_version == latest_version,
            "total_migrations": len(result),
            "migrations": [
                {"version": r[0], "applied_at": r[1].isoformat() if r[1] else None}
                for r in result
            ],
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
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                description VARCHAR,
                created_at TIMESTAMP DEFAULT current_timestamp,
                updated_at TIMESTAMP DEFAULT current_timestamp
            )
        """
        )

        # Repositories table
        self.conn.execute(
            """
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
        """
        )

        # Links table (relationships between repositories)
        self.conn.execute(
            """
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
        """
        )

        # System logs table for centralized logging
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                log_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT current_timestamp,
                level VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                message VARCHAR NOT NULL,
                context JSON
            )
        """
        )

        # Create indexes for common queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_project ON repositories(project_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_project ON links(project_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_repo_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_repo_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)"
        )

        logger.info("Created tables and indexes")

    async def execute_write(self, query: str, params: tuple = ()) -> Any:
        """
        Execute a write query with lock serialization.

        Uses asyncio.Lock to prevent concurrent writes which could cause
        DuckDB locking errors.

        Triggers snapshot creation after successful write for in-memory mode.

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
                result = self.conn.execute(query, params)

                # Mark that data has changed and trigger snapshot (in-memory mode)
                if self._is_memory_mode:
                    self._pending_snapshot = True
                    # Trigger snapshot creation asynchronously
                    asyncio.create_task(self._trigger_snapshot_on_write())

                return result
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

    async def _trigger_snapshot_on_write(self) -> None:
        """
        Trigger snapshot creation after write operations.

        Uses a small delay to batch multiple rapid writes into a single snapshot.
        """
        if not self._is_memory_mode or not self.snapshot_manager:
            return

        # Small delay to batch rapid writes (e.g., bulk inserts)
        await asyncio.sleep(1.0)

        # Only create snapshot if still pending (not already created by another write)
        if self._pending_snapshot:
            self._pending_snapshot = False
            try:
                logger.info(
                    "[EVENT-DRIVEN] Data changed detected, triggering snapshot creation..."
                )
                snapshot_path = self.create_snapshot()
                if snapshot_path:
                    logger.info(
                        f"[EVENT-DRIVEN] ✓ Snapshot saved: {os.path.basename(snapshot_path)}"
                    )
                else:
                    logger.warning("[EVENT-DRIVEN] Snapshot creation returned None")
            except Exception as e:
                logger.error(f"[EVENT-DRIVEN] ✗ Failed to create snapshot: {e}")

    def create_snapshot(self) -> Optional[str]:
        """
        Create a snapshot of the current database state.

        Only applicable for in-memory mode with snapshots enabled.

        Returns:
            Path to created snapshot, or None if not in snapshot mode
        """
        if not self._is_memory_mode or not self.snapshot_manager:
            logger.debug(
                "Snapshots not enabled (persistent mode or snapshots disabled)"
            )
            return None

        if not self.conn:
            logger.warning("Cannot create snapshot: database not connected")
            return None

        try:
            snapshot_path = self.snapshot_manager.create_snapshot(self.conn)
            # Cleanup old snapshots
            self.snapshot_manager.cleanup_old_snapshots()
            return snapshot_path
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return None

    def close(self) -> None:
        """Close DuckDB connection with snapshot creation for in-memory mode."""
        if self.conn:
            # Create final snapshot before closing (in-memory mode only)
            if self._is_memory_mode and self.snapshot_manager:
                try:
                    logger.info("Creating final snapshot before shutdown...")
                    snapshot_path = self.create_snapshot()
                    if snapshot_path:
                        logger.info(
                            f"Final snapshot created: {os.path.basename(snapshot_path)}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to create final snapshot: {e}")

            # For persistent mode: Execute CHECKPOINT to flush WAL
            if not self._is_memory_mode:
                try:
                    logger.info("Executing DuckDB CHECKPOINT before closing...")
                    self.conn.execute("CHECKPOINT")
                    logger.info("DuckDB CHECKPOINT completed successfully")
                except Exception as e:
                    logger.warning(f"Failed to execute CHECKPOINT during close: {e}")

            try:
                self.conn.close()
                self.conn = None
                self._initialized = False
                logger.info("DuckDB connection closed")
            except Exception as e:
                logger.error(f"Error closing DuckDB connection: {e}")
                # Ensure state is reset even if close fails
                self.conn = None
                self._initialized = False

    async def store_chat_artifact(
        self,
        session_id: str,
        message_id: str,
        artifact_type: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Store a chat artifact (e.g., graph data) for a specific message.

        Uses INSERT OR REPLACE to support idempotent updates.

        Args:
            session_id: Chat session identifier
            message_id: Message identifier within the session
            artifact_type: Type of artifact (e.g., "graph")
            data: Artifact data as a dictionary (will be JSON-serialized)
        """
        import json

        json_data = json.dumps(data)
        await self.execute_write(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (session_id, message_id, artifact_type)
            DO UPDATE SET artifact_data = EXCLUDED.artifact_data
            """,
            (session_id, message_id, artifact_type, json_data),
        )
        logger.debug(
            "Stored chat artifact: session=%s, message=%s, type=%s",
            session_id,
            message_id,
            artifact_type,
        )

    def get_chat_artifact(
        self,
        session_id: str,
        message_id: str,
        artifact_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chat artifact for a specific message.

        Args:
            session_id: Chat session identifier
            message_id: Message identifier within the session
            artifact_type: Type of artifact (e.g., "graph")

        Returns:
            Artifact data as a dictionary, or None if not found
        """
        import json

        result = self.fetchone(
            """
            SELECT artifact_data
            FROM chat_artifacts
            WHERE session_id = ? AND message_id = ? AND artifact_type = ?
            """,
            (session_id, message_id, artifact_type),
        )
        if result and result[0]:
            try:
                return json.loads(result[0])
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse chat artifact JSON: session=%s, message=%s",
                    session_id,
                    message_id,
                )
                return None
        return None

    async def cleanup_old_chat_artifacts(self, retention_days: int) -> int:
        """
        Delete chat artifacts older than the specified retention period.

        Args:
            retention_days: Number of days to retain artifacts

        Returns:
            Number of artifacts deleted
        """
        result = await self.execute_write(
            """
            DELETE FROM chat_artifacts
            WHERE created_at < CURRENT_TIMESTAMP - INTERVAL ? DAY
            """,
            (retention_days,),
        )
        deleted_count = result.rowcount if hasattr(result, "rowcount") else 0
        if deleted_count > 0:
            logger.info(
                "Cleaned up %d chat artifacts older than %d days",
                deleted_count,
                retention_days,
            )
        return deleted_count
    
    async def initialize_pool(self) -> None:
        """
        Initialize connection pool asynchronously.
        
        Phase 1: This method should be called in async context to properly
        initialize the connection pool and start health check tasks.
        
        Only applicable when connection pool is enabled.
        """
        if not self._enable_pool or not self._pool:
            logger.warning("Connection pool not enabled, skipping async initialization")
            return
        
        if self._pool._health_check_task is not None:
            logger.info("Connection pool already initialized")
            return
        
        logger.info("Initializing connection pool asynchronously...")
        await self._pool.initialize()
        logger.info("Connection pool initialized successfully")
    
    def transaction(self):
        """
        Get a transaction context for database operations.
        
        Phase 2: Provides ACID transaction support with automatic rollback on errors.
        Supports both connection pool and singleton modes.
        
        Usage:
            async with client.transaction() as tx:
                await tx.execute("INSERT INTO ...")
                await tx.execute("UPDATE ...")
                # Automatically commits on success, rolls back on error
        
        Returns:
            DuckDBTransaction: Transaction context manager
        
        Raises:
            RuntimeError: If transactions are not available
        """
        if not TRANSACTIONS_AVAILABLE:
            raise RuntimeError(
                "Transaction support not available. "
                "Ensure src.storage.duckdb_transactions is installed."
            )
        
        if self._enable_pool and self._pool:
            # Pool mode: Get connection from pool
            from contextlib import asynccontextmanager
            
            @asynccontextmanager
            async def _pool_transaction():
                async with self._pool.get_connection() as pooled_conn:
                    async with DuckDBTransaction(pooled_conn.connection) as tx:
                        yield tx
            
            return _pool_transaction()
        else:
            # Singleton mode: Use direct connection
            if not self.conn:
                raise RuntimeError("Database connection not initialized")
            
            return DuckDBTransaction(self.conn)

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
        raise RuntimeError(
            "DuckDB client not initialized. Call initialize_duckdb() first."
        )
    return _duckdb_client


def initialize_duckdb(
    db_path: str = "data/metadata.duckdb",
    enable_snapshots: bool = True,
    snapshot_keep_count: int = 5,
    snapshots_dir: str = "data/snapshots",
    # Phase 1: Connection pool parameters
    enable_connection_pool: Optional[bool] = None,
    pool_config: Optional[Dict[str, Any]] = None,
) -> DuckDBClient:
    """
    Initialize global DuckDB client.
    
    Phase 1: Supports optional connection pooling via environment variables.

    Args:
        db_path: Path to DuckDB database file, or ":memory:" for in-memory.
        enable_snapshots: Enable automatic snapshots for in-memory mode.
        snapshot_keep_count: Number of snapshots to retain
        snapshots_dir: Directory for snapshot storage
        enable_connection_pool: Enable connection pooling (None = from env var)
        pool_config: Connection pool configuration dict

    Returns:
        Initialized DuckDBClient instance
    """
    global _duckdb_client
    if _duckdb_client is not None and _duckdb_client.is_initialized:
        logger.warning("DuckDB client already initialized")
        return _duckdb_client

    # Phase 1: Check if connection pool is enabled
    if enable_connection_pool is None:
        enable_connection_pool = os.getenv("ENABLE_CONNECTION_POOL", "false").lower() == "true"
    
    # Build pool configuration from environment if not provided
    if enable_connection_pool and pool_config is None:
        pool_config = {
            "max_connections": int(os.getenv("CONNECTION_POOL_MAX_SIZE", "5")),
            "min_connections": int(os.getenv("CONNECTION_POOL_MIN_SIZE", "1")),
            "connection_timeout": float(os.getenv("CONNECTION_POOL_TIMEOUT", "30.0")),
            "max_idle_time": float(os.getenv("CONNECTION_POOL_MAX_IDLE_TIME", "300.0")),
            "health_check_interval": float(os.getenv("CONNECTION_POOL_HEALTH_CHECK_INTERVAL", "60.0")),
        }
        logger.info(f"Connection pool enabled with config: {pool_config}")
    
    _duckdb_client = DuckDBClient(
        db_path,
        enable_snapshots=enable_snapshots,
        snapshot_keep_count=snapshot_keep_count,
        snapshots_dir=snapshots_dir,
        enable_connection_pool=enable_connection_pool,
        pool_config=pool_config,
    )
    _duckdb_client.initialize()
    return _duckdb_client


def close_duckdb() -> None:
    """Close global DuckDB client."""
    global _duckdb_client
    if _duckdb_client is not None:
        _duckdb_client.close()
        _duckdb_client = None
