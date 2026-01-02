"""
SQL File Organizer - Separates SQL files into organized folder structure.

This module takes SQL files (which may contain multiple object definitions)
and separates them into individual files organized by object type:
- tables/
- views/
- functions/
- stored_procedures/
- triggers/
- indexes/
- schemas/
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json

from .sql_classifier import SQLClassifier, SQLObject, SQLObjectType


class SQLFileOrganizer:
    """
    Organizes SQL files by separating objects into type-specific folders.

    Features:
    - Separates mixed SQL files into individual object files
    - Organizes by object type (table, view, function, procedure, etc.)
    - Preserves metadata (source file, creation time)
    - Handles duplicate names with versioning
    - Generates manifest of separated files
    """

    # Folder mapping for each object type
    FOLDER_MAPPING = {
        SQLObjectType.TABLE: "tables",
        SQLObjectType.VIEW: "views",
        SQLObjectType.FUNCTION: "functions",
        SQLObjectType.PROCEDURE: "stored_procedures",
        SQLObjectType.TRIGGER: "triggers",
        SQLObjectType.INDEX: "indexes",
        SQLObjectType.SCHEMA: "schemas",
        SQLObjectType.UNKNOWN: "unknown",
    }

    def __init__(
        self,
        output_base_dir: str = "./data/separated_sql",
        dialect: str = "tsql",
        add_metadata_header: bool = True,
        overwrite_existing: bool = False,
        create_source_folders: bool = True,
    ):
        """
        Initialize the SQL file organizer.

        Args:
            output_base_dir: Base directory for separated SQL files
            dialect: SQL dialect for parsing
            add_metadata_header: Add header with metadata to separated files
            overwrite_existing: Whether to overwrite existing files
        """
        self.output_base_dir = Path(output_base_dir)
        self.dialect = dialect
        self.add_metadata_header = add_metadata_header
        self.overwrite_existing = overwrite_existing
        self.create_source_folders = create_source_folders
        self.classifier = SQLClassifier(dialect=dialect)

        # Statistics
        self.stats = {
            "files_processed": 0,
            "objects_separated": 0,
            "by_type": {obj_type.value: 0 for obj_type in SQLObjectType},
            "errors": [],
        }

    def create_folder_structure(self):
        """Create the organized folder structure."""
        print(f"Creating folder structure at: {self.output_base_dir}")

        for folder_name in self.FOLDER_MAPPING.values():
            folder_path = self.output_base_dir / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)

        print("[OK] Folder structure created")

    def organize_file(
        self, sql_file_path: str, source_folder_name: str = None
    ) -> Dict[str, List[str]]:
        """
        Organize a single SQL file by separating its objects.

        Args:
            sql_file_path: Path to the SQL file to organize
            source_folder_name: Optional name for the source file folder (defaults to filename without extension)

        Returns:
            Dictionary mapping object types to list of created files
        """
        print(f"\nProcessing: {sql_file_path}")

        sql_file_path = Path(sql_file_path)

        # Determine source folder name
        if source_folder_name is None:
            source_folder_name = sql_file_path.stem  # filename without extension

        if not sql_file_path.exists():
            error_msg = f"File not found: {sql_file_path}"
            self.stats["errors"].append(error_msg)
            print(f"[ERROR] {error_msg}")
            return {}

        # Read the SQL file
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            error_msg = f"Error reading {sql_file_path}: {e}"
            self.stats["errors"].append(error_msg)
            print(f"[ERROR] {error_msg}")
            return {}

        # Classify objects in the file
        try:
            objects = self.classifier.classify_file(content)
        except Exception as e:
            error_msg = f"Error classifying {sql_file_path}: {e}"
            self.stats["errors"].append(error_msg)
            print(f"[ERROR] {error_msg}")
            return {}

        if not objects:
            print(f"[WARN] No SQL objects found in {sql_file_path}")
            return {}

        print(f"Found {len(objects)} object(s)")

        # Separate each object
        created_files = {}
        for obj in objects:
            file_path = self._save_object(
                obj, source_file=sql_file_path.name, source_folder=source_folder_name
            )

            if file_path:
                obj_type = obj.object_type.value
                if obj_type not in created_files:
                    created_files[obj_type] = []
                created_files[obj_type].append(file_path)

                self.stats["objects_separated"] += 1
                self.stats["by_type"][obj_type] += 1

                print(
                    f"  [OK] {obj.object_type.value.upper()}: {obj.name} -> {file_path}"
                )

        self.stats["files_processed"] += 1

        return created_files

    def organize_directory(self, input_dir: str, pattern: str = "*.sql") -> Dict:
        """
        Organize all SQL files in a directory.

        Args:
            input_dir: Directory containing SQL files
            pattern: File pattern to match (default: *.sql)

        Returns:
            Summary of organized files
        """
        input_path = Path(input_dir)

        if not input_path.exists():
            print(f"[ERROR] Directory not found: {input_dir}")
            return {}

        # Find all SQL files
        sql_files = list(input_path.glob(pattern))

        if not sql_files:
            print(f"[WARN] No SQL files found in {input_dir}")
            return {}

        print(f"Found {len(sql_files)} SQL file(s) to process\n")
        print("=" * 60)

        # Process each file
        all_created_files = {}
        for sql_file in sql_files:
            created = self.organize_file(str(sql_file))

            # Merge results
            for obj_type, files in created.items():
                if obj_type not in all_created_files:
                    all_created_files[obj_type] = []
                all_created_files[obj_type].extend(files)

        # Generate manifest
        manifest_path = self._generate_manifest(all_created_files)

        print("\n" + "=" * 60)
        self._print_summary()

        return {
            "created_files": all_created_files,
            "manifest": manifest_path,
            "stats": self.stats,
        }

    def _save_object(
        self, obj: SQLObject, source_file: str, source_folder: str = None
    ) -> Optional[str]:
        """
        Save a SQL object to its designated folder.

        Args:
            obj: The SQL object to save
            source_file: Original source file name
            source_folder: Source file folder name (for organizing by source)

        Returns:
            Path to the created file, or None if failed
        """
        # Determine target folder
        folder_name = self.FOLDER_MAPPING.get(obj.object_type, "unknown")

        if self.create_source_folders and source_folder:
            # Create folder structure: output_base_dir/source_folder_name/object_type/
            target_dir = self.output_base_dir / source_folder / folder_name
        else:
            # Create folder structure: output_base_dir/object_type/
            target_dir = self.output_base_dir / folder_name

        # Ensure directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        base_filename = obj.get_filename()
        target_path = target_dir / base_filename

        # Handle duplicates
        if target_path.exists() and not self.overwrite_existing:
            target_path = self._get_unique_filename(target_path)

        # Prepare content
        content = self._prepare_file_content(obj, source_file)

        # Write file
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return str(target_path.relative_to(self.output_base_dir))
        except Exception as e:
            error_msg = f"Error writing {target_path}: {e}"
            self.stats["errors"].append(error_msg)
            print(f"  [ERROR] {error_msg}")
            return None

    def _prepare_file_content(self, obj: SQLObject, source_file: str) -> str:
        """Prepare the content to write to file, including metadata header."""
        lines = []

        if self.add_metadata_header:
            lines.append("-- ============================================")
            lines.append(f"-- Object Type: {obj.object_type.value.upper()}")
            lines.append(f"-- Object Name: {obj.get_full_name()}")
            lines.append(f"-- Source File: {source_file}")
            lines.append(
                f"-- Separated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            lines.append(f"-- Dialect: {self.dialect}")
            lines.append("-- ============================================")
            lines.append("")

        lines.append(obj.sql_content)

        # Ensure file ends with newline
        if not obj.sql_content.endswith("\n"):
            lines.append("")

        return "\n".join(lines)

    def _get_unique_filename(self, base_path: Path) -> Path:
        """Generate a unique filename if the base path already exists."""
        counter = 1
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent

        while True:
            new_name = f"{stem}_v{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

    def _generate_manifest(self, created_files: Dict[str, List[str]]) -> str:
        """Generate a manifest file documenting the separation."""
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "output_directory": str(self.output_base_dir),
            "dialect": self.dialect,
            "statistics": self.stats,
            "files_by_type": created_files,
        }

        manifest_path = self.output_base_dir / "separation_manifest.json"

        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            print(f"\n[OK] Manifest created: {manifest_path}")
            return str(manifest_path)
        except Exception as e:
            print(f"[WARN] Could not create manifest: {e}")
            return ""

    def _print_summary(self):
        """Print a summary of the organization process."""
        print("\n=== SEPARATION SUMMARY ===")
        print("=" * 60)
        print(f"Files Processed:     {self.stats['files_processed']}")
        print(f"Objects Separated:   {self.stats['objects_separated']}")
        print("\nBy Object Type:")

        for obj_type, count in self.stats["by_type"].items():
            if count > 0:
                folder = self.FOLDER_MAPPING.get(SQLObjectType(obj_type), obj_type)
                print(f"  {obj_type.upper():<20} {count:>3} -> {folder}/")

        if self.stats["errors"]:
            print(f"\n[WARN] Errors Encountered: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:  # Show first 5
                print(f"  - {error}")
            if len(self.stats["errors"]) > 5:
                print(f"  ... and {len(self.stats['errors']) - 5} more")

        print(f"\n[OK] Output Directory: {self.output_base_dir}")
        print("=" * 60)

    def get_stats(self) -> Dict:
        """Get organization statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            "files_processed": 0,
            "objects_separated": 0,
            "by_type": {obj_type.value: 0 for obj_type in SQLObjectType},
            "errors": [],
        }


def organize_sql_files(
    input_dir: str,
    output_dir: str = "./data/separated_sql",
    dialect: str = "tsql",
    pattern: str = "*.sql",
    create_source_folders: bool = True,
) -> Dict:
    """
    Convenience function to organize SQL files.

    Args:
        input_dir: Directory containing SQL files to organize
        output_dir: Directory for separated output files
        dialect: SQL dialect (tsql, postgres, mysql, etc.)
        pattern: File pattern to match

    Returns:
        Dictionary with organization results
    """
    organizer = SQLFileOrganizer(
        output_base_dir=output_dir,
        dialect=dialect,
        add_metadata_header=True,
        overwrite_existing=False,
        create_source_folders=create_source_folders,
    )

    # Create folder structure
    organizer.create_folder_structure()

    # Organize files
    results = organizer.organize_directory(input_dir, pattern=pattern)

    return results


if __name__ == "__main__":
    import sys

    # Example usage
    if len(sys.argv) > 1:
        input_directory = sys.argv[1]
        output_directory = sys.argv[2] if len(sys.argv) > 2 else "./data/separated_sql"

        print("SQL File Organizer")
        print("=" * 60)
        print(f"Input:  {input_directory}")
        print(f"Output: {output_directory}")
        print("=" * 60)

        results = organize_sql_files(
            input_dir=input_directory, output_dir=output_directory
        )
    else:
        print("Usage: python sql_file_organizer.py <input_dir> [output_dir]")
        print("\nExample:")
        print("  python sql_file_organizer.py ./data ./data/separated_sql")
