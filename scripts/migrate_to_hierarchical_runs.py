"""
Migration script for structure-data-outputs OpenSpec change.

Migrates legacy files from data/ root to data/archive/{date}/
Preserves: metadata.duckdb, metadata.duckdb.wal, contexts/

New runs will use: data/{ProjectName}/{YYYYMMDD_HHmmss}_{seq}_{action}/

Usage:
    python scripts/migrate_to_hierarchical_runs.py --dry-run  # Preview
    python scripts/migrate_to_hierarchical_runs.py            # Execute
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


PRESERVED_ITEMS = {
    "metadata.duckdb",
    "metadata.duckdb.wal",
    "contexts",
    "archive",  # Don't re-archive
}


def is_new_structure_directory(path: Path) -> bool:
    """Check if directory appears to be in new hierarchical structure."""
    if not path.is_dir():
        return False

    # Check for timestamp-based subdirectories
    for subdir in path.iterdir():
        if subdir.is_dir():
            # Pattern: YYYYMMDD_HHmmss_NNN_action
            parts = subdir.name.split("_")
            if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 8:
                return True
    return False


def get_legacy_files(data_dir: Path) -> list[Path]:
    """Identify legacy files/dirs to migrate."""
    legacy_items = []

    for item in data_dir.iterdir():
        # Skip preserved items
        if item.name in PRESERVED_ITEMS:
            continue

        # Skip new structure directories
        if item.is_dir() and is_new_structure_directory(item):
            logger.info(f"Skipping new structure: {item.name}")
            continue

        legacy_items.append(item)

    return legacy_items


def create_archive_dir(data_dir: Path) -> Path:
    """Create archive directory with today's date."""
    today = datetime.utcnow().strftime("%Y%m%d")
    archive_dir = data_dir / "archive" / today
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


def migrate_item(source: Path, archive_dir: Path, dry_run: bool) -> bool:
    """Migrate a single file or directory."""
    dest = archive_dir / source.name

    if dry_run:
        logger.info(f"[DRY-RUN] {source.name} → archive/{archive_dir.name}/{dest.name}")
        return True

    try:
        if source.is_file():
            shutil.copy2(source, dest)
        else:
            shutil.copytree(source, dest, dirs_exist_ok=True)
        logger.info(f"Migrated: {source.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to migrate {source.name}: {e}")
        return False


def verify_and_cleanup(
    legacy_items: list[Path], archive_dir: Path, dry_run: bool
) -> int:
    """Verify migration and remove originals."""
    removed = 0

    for item in legacy_items:
        archived = archive_dir / item.name

        if dry_run:
            logger.info(f"[DRY-RUN] Would remove: {item.name}")
            removed += 1
            continue

        # Verify archived
        if not archived.exists():
            logger.warning(f"Not archived, skipping removal: {item.name}")
            continue

        # Remove original
        try:
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)
            removed += 1
        except Exception as e:
            logger.error(f"Failed to remove {item.name}: {e}")

    return removed


def log_migration(archive_dir: Path, count: int, dry_run: bool):
    """Log migration to DuckDB."""
    if dry_run:
        return

    try:
        from src.storage.duckdb_client import get_duckdb_client
        import uuid
        import json

        client = get_duckdb_client()

        context = {
            "migration": "structure-data-outputs",
            "archive_location": str(archive_dir),
            "files_migrated": count,
            "timestamp": datetime.utcnow().isoformat(),
        }

        client.execute_write(
            """INSERT INTO system_logs (log_id, level, source, message, context)
               VALUES (?, 'INFO', 'migration', ?, ?)""",
            (str(uuid.uuid4()), f"Migrated {count} legacy files", json.dumps(context)),
        )
        logger.info("Logged to DuckDB")
    except Exception as e:
        logger.warning(f"Could not log to DuckDB: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate to hierarchical runs structure"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without changes"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data"), help="Data directory"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Keep originals after migration"
    )

    args = parser.parse_args()
    data_dir = args.data_dir.resolve()

    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return 1

    logger.info("=" * 60)
    logger.info(f"Hierarchical Runs Migration")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"Data dir: {data_dir}")
    logger.info("")

    # Step 1: Find legacy items
    logger.info("Step 1: Finding legacy files...")
    legacy_items = get_legacy_files(data_dir)

    if not legacy_items:
        logger.info("No legacy files found. Already migrated!")
        return 0

    logger.info(f"Found {len(legacy_items)} items to migrate:")
    for item in legacy_items:
        item_type = "DIR" if item.is_dir() else "FILE"
        logger.info(f"  [{item_type}] {item.name}")
    logger.info("")

    # Step 2: Create archive
    logger.info("Step 2: Creating archive directory...")
    archive_dir = create_archive_dir(data_dir)
    logger.info(f"Archive: {archive_dir}")
    logger.info("")

    # Step 3: Migrate
    logger.info("Step 3: Migrating files...")
    success_count = sum(
        1 for item in legacy_items if migrate_item(item, archive_dir, args.dry_run)
    )
    logger.info(f"Migrated: {success_count}/{len(legacy_items)}")
    logger.info("")

    # Step 4: Verify and cleanup
    if not args.no_cleanup:
        logger.info("Step 4: Cleaning up originals...")
        removed = verify_and_cleanup(legacy_items, archive_dir, args.dry_run)
        logger.info(f"Removed: {removed} items")
        logger.info("")

    # Step 5: Log
    logger.info("Step 5: Logging migration...")
    log_migration(archive_dir, success_count, args.dry_run)
    logger.info("")

    logger.info("=" * 60)
    logger.info("Migration Complete!")
    logger.info("=" * 60)
    logger.info(f"Archive location: {archive_dir}")
    logger.info("")
    logger.info("Preserved in data/:")
    logger.info("  - metadata.duckdb")
    logger.info("  - contexts/")
    logger.info("")
    logger.info("New uploads will use:")
    logger.info("  - data/{ProjectName}/{YYYYMMDD_HHmmss}_{seq}_{action}/")
    logger.info("")

    if args.dry_run:
        logger.info("NOTE: This was a DRY-RUN. Remove --dry-run to execute.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
