"""
Snapshot Manager for DuckDB in-memory database.

Provides automatic snapshot creation, loading, and management for persistence
of in-memory DuckDB databases across container restarts.

Key Features:
- Create snapshots using DuckDB native EXPORT DATABASE
- Load snapshots using DuckDB native IMPORT DATABASE
- Track data changes to avoid redundant snapshots
- Automatic cleanup of old snapshots (keep N most recent)
- List and retrieve snapshot metadata
"""

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import duckdb

logger = logging.getLogger(__name__)


class SnapshotManager:
    """
    Manages DuckDB database snapshots for in-memory persistence.

    Snapshots are stored in data/snapshots/ directory with naming format:
    snapshot_YYYYMMDD_HHMMSS.duckdb

    Args:
        snapshots_dir: Directory to store snapshots (default: data/snapshots)
        keep_count: Number of recent snapshots to retain (default: 5)
    """

    def __init__(self, snapshots_dir: str = "data/snapshots", keep_count: int = 5):
        self.snapshots_dir = Path(snapshots_dir)
        self.keep_count = keep_count
        self._last_snapshot_hash: Optional[str] = None

        # Ensure snapshots directory exists
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"SnapshotManager initialized with directory: {self.snapshots_dir}")

    def create_snapshot(self, db_conn: duckdb.DuckDBPyConnection) -> str:
        """
        Create a snapshot of the current database state.

        Args:
            db_conn: Active DuckDB connection to snapshot

        Returns:
            Path to the created snapshot file

        Raises:
            Exception: If snapshot creation fails
        """
        # Generate timestamp-based snapshot filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"snapshot_{timestamp}.duckdb"
        snapshot_path = self.snapshots_dir / snapshot_name

        try:
            start_time = datetime.utcnow()
            logger.info(f"[Snapshot] Creating snapshot: {snapshot_name}...")

            # Use DuckDB's EXPORT DATABASE for ACID-compliant snapshot
            export_path = str(snapshot_path)
            db_conn.execute(f"EXPORT DATABASE '{export_path}'")

            # Update last snapshot hash
            self._last_snapshot_hash = self._compute_data_hash(db_conn)

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[Snapshot] ✓ COMPLETED: {snapshot_name} ({elapsed:.2f}s)")
            return str(snapshot_path)

        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            # Clean up partial snapshot if exists
            if snapshot_path.exists():
                try:
                    if snapshot_path.is_dir():
                        shutil.rmtree(snapshot_path)
                    else:
                        snapshot_path.unlink()
                except Exception:
                    pass
            raise

    def load_snapshot(
        self, db_conn: duckdb.DuckDBPyConnection, snapshot_path: str
    ) -> None:
        """
        Load a snapshot into the provided database connection.

        Args:
            db_conn: Active DuckDB connection to load into
            snapshot_path: Path to snapshot file to load

        Raises:
            FileNotFoundError: If snapshot file doesn't exist
            Exception: If snapshot loading fails
        """
        snapshot_file = Path(snapshot_path)

        if not snapshot_file.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

        try:
            logger.info(f"Loading snapshot: {snapshot_file.name}")

            # Use DuckDB's IMPORT DATABASE to load snapshot
            import_path = str(snapshot_file)
            db_conn.execute(f"IMPORT DATABASE '{import_path}'")

            # Update last snapshot hash after loading
            self._last_snapshot_hash = self._compute_data_hash(db_conn)

            logger.info(f"Snapshot loaded successfully: {snapshot_file.name}")

        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            raise

    def list_snapshots(self) -> List[Dict[str, any]]:
        """
        List all available snapshots with metadata.

        Returns:
            List of snapshot metadata dicts, sorted by timestamp (descending).
            Each dict contains: id, timestamp, file_size_bytes, record_count, file_path
        """
        snapshots = []

        # Find all snapshot files
        for snapshot_file in self.snapshots_dir.glob("snapshot_*.duckdb"):
            try:
                # Extract timestamp from filename
                timestamp_str = snapshot_file.stem.replace("snapshot_", "")
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                # Get record count from snapshot
                record_count = self._get_snapshot_record_count(snapshot_file)

                snapshots.append(
                    {
                        "id": timestamp_str,
                        "timestamp": timestamp.isoformat(),
                        "file_size_bytes": self._get_snapshot_size(snapshot_file),
                        "record_count": record_count,
                        "file_path": str(snapshot_file),
                    }
                )
            except (ValueError, OSError) as e:
                logger.warning(
                    f"Skipping invalid snapshot file {snapshot_file.name}: {e}"
                )
                continue

        # Sort by timestamp descending (newest first)
        snapshots.sort(key=lambda s: s["timestamp"], reverse=True)

        logger.debug(f"Found {len(snapshots)} snapshots")
        return snapshots

    def get_latest_snapshot(self) -> Optional[str]:
        """
        Get the path to the most recent snapshot.

        Returns:
            Path to latest snapshot file, or None if no snapshots exist
        """
        snapshots = self.list_snapshots()
        if not snapshots:
            logger.info("No snapshots found")
            return None

        latest = snapshots[0]  # Already sorted descending
        logger.info(f"Latest snapshot: {latest['id']}")
        return latest["file_path"]

    def cleanup_old_snapshots(self) -> int:
        """
        Remove old snapshots, keeping only the N most recent.

        Returns:
            Number of snapshots deleted
        """
        snapshots = self.list_snapshots()

        if len(snapshots) <= self.keep_count:
            logger.debug(
                f"No cleanup needed: {len(snapshots)} snapshots (keep {self.keep_count})"
            )
            return 0

        # Delete older snapshots beyond keep_count
        deleted_count = 0
        for snapshot in snapshots[self.keep_count :]:
            try:
                snapshot_file = Path(snapshot["file_path"])
                if snapshot_file.is_dir():
                    shutil.rmtree(snapshot_file)
                else:
                    snapshot_file.unlink()
                logger.info(f"Deleted old snapshot: {snapshot['id']}")
                deleted_count += 1
            except OSError as e:
                logger.warning(f"Failed to delete snapshot {snapshot['id']}: {e}")

        logger.info(f"Cleanup complete: deleted {deleted_count} old snapshots")
        return deleted_count

    def has_data_changed(self, db_conn: duckdb.DuckDBPyConnection) -> bool:
        """
        Check if database data has changed since last snapshot.

        Uses a lightweight hash of row counts per table to detect changes.
        Note: This detects additions/deletions but not modifications to existing rows.

        Args:
            db_conn: Active DuckDB connection to check

        Returns:
            True if data has changed, False otherwise
        """
        current_hash = self._compute_data_hash(db_conn)

        if self._last_snapshot_hash is None:
            logger.debug("No previous snapshot hash, data considered changed")
            return True

        changed = current_hash != self._last_snapshot_hash
        logger.debug(f"Data changed: {changed}")
        return changed

    def _compute_data_hash(self, db_conn: duckdb.DuckDBPyConnection) -> str:
        """
        Compute a hash representing the current database state.

        Uses row counts from all tables as a lightweight change indicator.

        Args:
            db_conn: Active DuckDB connection

        Returns:
            MD5 hash of table row counts
        """
        try:
            # Get list of all tables
            tables_result = db_conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()

            tables = [row[0] for row in tables_result]

            # Count rows in each table
            counts = {}
            for table in tables:
                count = db_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                counts[table] = count

            # Compute hash of counts
            counts_json = json.dumps(counts, sort_keys=True)
            hash_value = hashlib.md5(counts_json.encode()).hexdigest()

            logger.debug(f"Data hash computed: {hash_value} (tables: {counts})")
            return hash_value

        except Exception as e:
            logger.warning(f"Failed to compute data hash: {e}")
            # Return a random hash to trigger snapshot on error
            return hashlib.md5(str(datetime.utcnow()).encode()).hexdigest()

    @staticmethod
    def _get_snapshot_size(snapshot_path: Path) -> int:
        """Compute total size of snapshot directory or file."""
        if not snapshot_path.exists():
            return 0

        if snapshot_path.is_file():
            return snapshot_path.stat().st_size

        total_size = 0
        for root, _, files in os.walk(snapshot_path):
            for file_name in files:
                file_path = Path(root) / file_name
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    continue
        return total_size

    @staticmethod
    def _get_snapshot_record_count(snapshot_path: Path) -> int:
        """
        Compute total row count across all tables in a snapshot.
        
        Handles missing or corrupted snapshots gracefully.
        Re-runnable and idempotent.
        """
        if not snapshot_path.exists():
            logger.debug(f"Snapshot path does not exist: {snapshot_path}")
            return 0
        
        # Check if snapshot directory has required files
        if snapshot_path.is_dir():
            schema_file = snapshot_path / "schema.sql"
            if not schema_file.exists():
                logger.debug(
                    f"Snapshot {snapshot_path.name} missing schema.sql, "
                    "cannot compute record count (returning 0)"
                )
                return 0

        conn = None
        try:
            conn = duckdb.connect(":memory:")
            
            # Import the snapshot
            import_path = str(snapshot_path)
            conn.execute(f"IMPORT DATABASE '{import_path}'")

            # Get all tables
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            table_names = [row[0] for row in tables]

            # Count total rows
            total_rows = 0
            for table in table_names:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    total_rows += count
                except Exception as e:
                    logger.debug(f"Could not count rows in table {table}: {e}")
                    continue

            logger.debug(f"Snapshot {snapshot_path.name} has {total_rows} total rows")
            return total_rows
            
        except Exception as e:
            # Log at debug level to avoid spamming logs
            logger.debug(
                f"Could not compute record count for {snapshot_path.name}: {e}. "
                "This is normal for incomplete or corrupted snapshots."
            )
            return 0
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
