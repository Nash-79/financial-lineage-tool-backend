"""
Data folder structure migration script.

Migrates data from the old flat structure to the new hierarchical structure
organized by database name.

Old structure:
    data/
    ├── AdventureWorksLT-All.sql
    ├── sql_embeddings.json
    ├── graph_export.json
    └── separated_sql/
        ├── tables/
        └── views/

New structure:
    data/
    └── adventureworks-lt-all/
        ├── raw/
        │   └── AdventureWorksLT-All.sql
        ├── embeddings/
        │   └── sql_embeddings.json
        ├── graph/
        │   └── graph_export.json
        └── separated/
            ├── tables/
            └── views/

Usage:
    # Dry run (shows what would be moved)
    python scripts/migrate_data_structure.py --dry-run

    # Execute migration with backup
    python scripts/migrate_data_structure.py --execute --backup

    # Validate migration
    python scripts/migrate_data_structure.py --validate

    # Rollback from backup
    python scripts/migrate_data_structure.py --rollback backup.tar.gz
"""

import argparse
import json
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.data_paths import (
    DataPathManager,
    detect_database_name,
    normalize_database_name,
)


class DataMigrator:
    """Handles migration of data from old flat structure to new hierarchical structure."""

    def __init__(self, data_root: Path = Path("./data")):
        """
        Initialize the migrator.

        Args:
            data_root: Root data directory (default: ./data)
        """
        self.data_root = data_root
        self.migration_plan: List[Dict] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def analyze_current_structure(self) -> Dict[str, List[Path]]:
        """
        Analyze current data folder and categorize files.

        Returns:
            Dictionary mapping file categories to lists of file paths
        """
        categories = {
            "raw_sql": [],
            "embeddings": [],
            "graph": [],
            "metadata": [],
            "separated_dirs": [],
            "cache": [],
            "unknown": [],
        }

        if not self.data_root.exists():
            print(f"[ERROR] Data root does not exist: {self.data_root}")
            return categories

        for item in self.data_root.iterdir():
            if item.name == ".cache":
                categories["cache"].append(item)
            elif item.name == "README.md":
                # Skip README
                continue
            elif item.is_file():
                # Categorize files
                if item.suffix == ".sql":
                    categories["raw_sql"].append(item)
                elif "embedding" in item.name.lower():
                    categories["embeddings"].append(item)
                elif "graph" in item.name.lower() or "cypher" in item.name.lower():
                    categories["graph"].append(item)
                elif "failed_ingestion" in item.name or "processing" in item.name:
                    categories["metadata"].append(item)
                else:
                    categories["unknown"].append(item)
            elif item.is_dir():
                # Check for separated SQL directories
                if item.name == "separated_sql" or item.name == "raw":
                    categories["separated_dirs"].append(item)
                elif item.name.startswith("."):
                    # Hidden directories (skip)
                    pass
                else:
                    # Could be database-specific folder (already migrated)
                    # or unknown directory
                    if any(
                        (item / cat).exists()
                        for cat in [
                            "raw",
                            "separated",
                            "embeddings",
                            "graph",
                            "metadata",
                        ]
                    ):
                        # Already in new structure
                        print(
                            f"ℹ️  Skipping already migrated database folder: {item.name}"
                        )
                    else:
                        categories["unknown"].append(item)

        return categories

    def create_migration_plan(self) -> bool:
        """
        Create a migration plan based on current structure.

        Returns:
            True if plan created successfully, False if errors occurred
        """
        categories = self.analyze_current_structure()
        self.migration_plan = []

        # Process raw SQL files
        for sql_file in categories["raw_sql"]:
            db_name = detect_database_name(sql_file)
            path_manager = DataPathManager(self.data_root, db_name)
            dest = path_manager.raw_path(sql_file.name, create_dir=False)

            self.migration_plan.append(
                {
                    "source": sql_file,
                    "dest": dest,
                    "category": "raw",
                    "database": db_name,
                    "action": "move",
                }
            )

        # Process embedding files
        for emb_file in categories["embeddings"]:
            # Try to detect database from filename or use default
            db_name = self._detect_database_for_file(emb_file, categories["raw_sql"])
            path_manager = DataPathManager(self.data_root, db_name)
            dest = path_manager.embeddings_path(emb_file.name, create_dir=False)

            self.migration_plan.append(
                {
                    "source": emb_file,
                    "dest": dest,
                    "category": "embeddings",
                    "database": db_name,
                    "action": "move",
                }
            )

        # Process graph files
        for graph_file in categories["graph"]:
            db_name = self._detect_database_for_file(graph_file, categories["raw_sql"])
            path_manager = DataPathManager(self.data_root, db_name)
            dest = path_manager.graph_path(graph_file.name, create_dir=False)

            self.migration_plan.append(
                {
                    "source": graph_file,
                    "dest": dest,
                    "category": "graph",
                    "database": db_name,
                    "action": "move",
                }
            )

        # Process metadata files
        for meta_file in categories["metadata"]:
            db_name = self._detect_database_for_file(meta_file, categories["raw_sql"])
            path_manager = DataPathManager(self.data_root, db_name)
            dest = path_manager.metadata_path(meta_file.name, create_dir=False)

            self.migration_plan.append(
                {
                    "source": meta_file,
                    "dest": dest,
                    "category": "metadata",
                    "database": db_name,
                    "action": "move",
                }
            )

        # Process separated_sql directory
        for sep_dir in categories["separated_dirs"]:
            if sep_dir.name == "separated_sql":
                self._process_separated_sql_dir(sep_dir, categories["raw_sql"])
            elif sep_dir.name == "raw":
                # Old raw directory - move contents
                self._process_raw_dir(sep_dir, categories["raw_sql"])

        # Warn about unknown files
        for unknown in categories["unknown"]:
            self.warnings.append(
                f"Unknown file/directory will not be migrated: {unknown}"
            )

        return len(self.errors) == 0

    def _detect_database_for_file(
        self, file_path: Path, raw_sql_files: List[Path]
    ) -> str:
        """
        Detect which database a file belongs to.

        Args:
            file_path: Path to the file
            raw_sql_files: List of raw SQL files to match against

        Returns:
            Database name (may be 'default' if can't determine)
        """
        # If there's only one SQL file, assume all files belong to that database
        if len(raw_sql_files) == 1:
            return detect_database_name(raw_sql_files[0])

        # Try to match by filename prefix
        for sql_file in raw_sql_files:
            db_name = detect_database_name(sql_file)
            # Check if file name contains database name
            if db_name.replace("-", "").lower() in file_path.name.lower():
                return db_name

        # Default fallback
        return "default"

    def _process_separated_sql_dir(
        self, sep_dir: Path, raw_sql_files: List[Path]
    ) -> None:
        """
        Process the separated_sql directory.

        Args:
            sep_dir: Path to separated_sql directory
            raw_sql_files: List of raw SQL files
        """
        # Check if it contains database-specific folders
        has_db_folders = any(
            (sep_dir / item.name).is_dir()
            for item in sep_dir.iterdir()
            if not item.name.endswith(".json")
        )

        if has_db_folders:
            # Structure: separated_sql/{DatabaseName}/{object_type}/
            for db_folder in sep_dir.iterdir():
                if db_folder.is_dir() and not db_folder.name.endswith(".json"):
                    db_name = normalize_database_name(db_folder.name)
                    path_manager = DataPathManager(self.data_root, db_name)

                    # Move object type folders
                    for object_type_dir in db_folder.iterdir():
                        if object_type_dir.is_dir():
                            dest = path_manager.separated_path(
                                object_type_dir.name, create_dir=False
                            )
                            self.migration_plan.append(
                                {
                                    "source": object_type_dir,
                                    "dest": dest,
                                    "category": "separated",
                                    "database": db_name,
                                    "action": "move_dir",
                                }
                            )
        else:
            # Structure: separated_sql/{object_type}/ (generic)
            db_name = self._detect_database_for_file(sep_dir, raw_sql_files)
            path_manager = DataPathManager(self.data_root, db_name)

            for object_type_dir in sep_dir.iterdir():
                if object_type_dir.is_dir():
                    dest = path_manager.separated_path(
                        object_type_dir.name, create_dir=False
                    )
                    self.migration_plan.append(
                        {
                            "source": object_type_dir,
                            "dest": dest,
                            "category": "separated",
                            "database": db_name,
                            "action": "move_dir",
                        }
                    )
                elif object_type_dir.name.endswith(".json"):
                    # Manifest file
                    dest = path_manager.separation_manifest_path(create_dir=False)
                    self.migration_plan.append(
                        {
                            "source": object_type_dir,
                            "dest": dest,
                            "category": "separated",
                            "database": db_name,
                            "action": "move",
                        }
                    )

    def _process_raw_dir(self, raw_dir: Path, raw_sql_files: List[Path]) -> None:
        """
        Process the old raw directory.

        Args:
            raw_dir: Path to raw directory
            raw_sql_files: List of raw SQL files
        """
        for sql_file in raw_dir.rglob("*.sql"):
            db_name = detect_database_name(sql_file)
            path_manager = DataPathManager(self.data_root, db_name)
            dest = path_manager.raw_path(sql_file.name, create_dir=False)

            self.migration_plan.append(
                {
                    "source": sql_file,
                    "dest": dest,
                    "category": "raw",
                    "database": db_name,
                    "action": "move",
                }
            )

    def print_migration_plan(self, dry_run: bool = True) -> None:
        """
        Print the migration plan.

        Args:
            dry_run: Whether this is a dry run
        """
        prefix = "[DRY RUN] " if dry_run else ""

        print(f"\n{'='*80}")
        print(f"{prefix}Migration Plan")
        print(f"{'='*80}\n")

        # Group by database
        by_database = {}
        for item in self.migration_plan:
            db = item["database"]
            if db not in by_database:
                by_database[db] = []
            by_database[db].append(item)

        for db_name, items in sorted(by_database.items()):
            print(f"\n[Database: {db_name}]")
            print(f"   {len(items)} items to migrate")

            for item in items:
                source = item["source"]
                dest = item["dest"]
                action = item["action"]

                if action == "move_dir":
                    print(
                        f"   DIR:  {source.relative_to(self.data_root)} -> {dest.relative_to(self.data_root)}/"
                    )
                else:
                    print(
                        f"   FILE: {source.relative_to(self.data_root)} -> {dest.relative_to(self.data_root)}"
                    )

        # Print warnings
        if self.warnings:
            print(f"\n[!] Warnings:")
            for warning in self.warnings:
                print(f"   {warning}")

        # Print summary
        print(f"\n{'='*80}")
        print(f"{prefix}Summary")
        print(f"{'='*80}")
        print(f"   Total items: {len(self.migration_plan)}")
        print(f"   Databases: {len(by_database)}")
        print(f"   Warnings: {len(self.warnings)}")
        print(f"   Errors: {len(self.errors)}")
        print()

    def execute_migration(self, backup: bool = True) -> bool:
        """
        Execute the migration plan.

        Args:
            backup: Whether to create a backup first

        Returns:
            True if migration succeeded, False otherwise
        """
        if backup:
            backup_file = self.create_backup()
            if backup_file:
                print(f"[OK] Backup created: {backup_file}")
            else:
                print(f"[ERROR] Backup failed, aborting migration")
                return False

        print(f"\n[*] Executing migration...")

        success_count = 0
        for item in self.migration_plan:
            try:
                source = item["source"]
                dest = item["dest"]
                action = item["action"]

                # Create destination directory
                dest.parent.mkdir(parents=True, exist_ok=True)

                if action == "move_dir":
                    # Move entire directory
                    if dest.exists():
                        # Merge contents
                        for child in source.rglob("*"):
                            if child.is_file():
                                rel_path = child.relative_to(source)
                                dest_file = dest / rel_path
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.move(str(child), str(dest_file))
                        # Remove empty source directory
                        if not any(source.iterdir()):
                            source.rmdir()
                    else:
                        shutil.move(str(source), str(dest))
                else:
                    # Move file
                    if dest.exists():
                        self.warnings.append(f"Destination exists, skipping: {dest}")
                        continue
                    shutil.move(str(source), str(dest))

                success_count += 1
                print(f"[+] Moved: {source.name}")

            except Exception as e:
                self.errors.append(f"Failed to move {source}: {e}")
                print(f"[-] Error moving {source.name}: {e}")

        # Clean up empty directories
        self._cleanup_empty_dirs()

        print(
            f"\n[OK] Migration complete: {success_count}/{len(self.migration_plan)} items migrated"
        )
        if self.errors:
            print(f"[ERROR] {len(self.errors)} errors occurred:")
            for error in self.errors:
                print(f"   {error}")
            return False

        return True

    def _cleanup_empty_dirs(self) -> None:
        """Remove empty directories after migration."""
        for item in self.data_root.iterdir():
            if (
                item.is_dir()
                and item.name not in [".cache", ".git"]
                and not item.name.startswith(".")
            ):
                try:
                    if not any(item.rglob("*")):
                        item.rmdir()
                        print(f"   [DEL] Removed empty directory: {item.name}")
                except Exception:
                    pass

    def create_backup(self) -> Path | None:
        """
        Create a compressed backup of the data folder.

        Returns:
            Path to backup file, or None if backup failed
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.data_root.parent / f"data_backup_{timestamp}.tar.gz"

        try:
            print(f"[*] Creating backup: {backup_file}")
            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(self.data_root, arcname="data")
            return backup_file
        except Exception as e:
            print(f"[ERROR] Backup failed: {e}")
            return None

    def validate_migration(self) -> bool:
        """
        Validate that migration completed successfully.

        Returns:
            True if validation passed, False otherwise
        """
        print(f"\n[*] Validating migration...")

        # Check that no files remain at root level (except .cache and README.md)
        root_files = []
        for item in self.data_root.iterdir():
            if item.is_file() and item.name != "README.md":
                root_files.append(item)
            elif (
                item.is_dir()
                and item.name not in [".cache"]
                and not item.name.startswith(".")
            ):
                # Check if it's a database folder (has expected subdirectories)
                has_structure = any(
                    (item / cat).exists()
                    for cat in ["raw", "separated", "embeddings", "graph", "metadata"]
                )
                if not has_structure:
                    root_files.append(item)

        if root_files:
            print(f"[ERROR] Validation failed: Files/folders remain at root:")
            for f in root_files:
                print(f"   - {f.name}")
            return False

        print(f"[OK] Validation passed: All files migrated to database folders")
        return True


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate data folder structure from flat to hierarchical organization"
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("./data"),
        help="Root data directory (default: ./data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually moving files",
    )
    parser.add_argument("--execute", action="store_true", help="Execute the migration")
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before migration (default: True)",
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Skip backup (not recommended)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate that migration completed successfully",
    )
    parser.add_argument("--rollback", type=Path, help="Rollback from a backup file")

    args = parser.parse_args()

    # Handle rollback
    if args.rollback:
        print(f"[*] Rolling back from backup: {args.rollback}")
        try:
            # Extract backup
            with tarfile.open(args.rollback, "r:gz") as tar:
                tar.extractall(args.data_root.parent)
            print(f"[OK] Rollback complete")
            return 0
        except Exception as e:
            print(f"[ERROR] Rollback failed: {e}")
            return 1

    # Create migrator
    migrator = DataMigrator(data_root=args.data_root)

    # Validation only mode
    if args.validate:
        success = migrator.validate_migration()
        return 0 if success else 1

    # Create migration plan
    if not migrator.create_migration_plan():
        print(f"[ERROR] Failed to create migration plan")
        return 1

    # Dry run mode (default)
    if args.dry_run or not args.execute:
        migrator.print_migration_plan(dry_run=True)
        if not args.execute:
            print("\n[INFO] To execute the migration, run with --execute flag")
        return 0

    # Execute migration
    if args.execute:
        migrator.print_migration_plan(dry_run=False)
        print(f"\n[WARNING] This will modify the data folder structure!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("[CANCELLED] Migration cancelled")
            return 1

        backup = not args.no_backup if not args.no_backup else args.backup
        success = migrator.execute_migration(backup=backup)

        if success:
            print(f"\n[OK] Migration completed successfully!")
            print(f"\n[INFO] Run with --validate to verify the migration")
            return 0
        else:
            print(f"\n[ERROR] Migration failed")
            return 1


if __name__ == "__main__":
    sys.exit(main())
