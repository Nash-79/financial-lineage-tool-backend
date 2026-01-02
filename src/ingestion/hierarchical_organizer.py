"""
Hierarchical SQL Organizer - Creates hierarchical folder structure for SQL objects.

This organizer creates a nested structure where each table/view gets its own folder
with subfolders for related objects:

AdventureWorksLT-All/
  tables/
    ProductCategory/
      ProductCategory.sql
      constraints/
        DF_ProductCategory_rowguid.sql
      indexes/
        PK_ProductCategory_ProductCategoryID.sql
      foreign_keys/
        FK_ProductCategory_Parent.sql
      check_constraints/
        CK_ProductCategory_Name.sql
  views/
    vProductAndDescription/
      vProductAndDescription.sql
      indexes/
        IX_vProductAndDescription.sql  (for indexed views)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from .enhanced_sql_parser import EnhancedSQLParser, SQLServerObject, SQLServerObjectType
from ..utils.data_paths import DataPathManager, detect_database_name


class HierarchicalOrganizer:
    """
    Organizes SQL objects into hierarchical folder structure.

    Features:
    - Each table/view/function/procedure gets its own folder
    - Related objects (constraints, indexes) grouped with parent
    - Metadata preserved
    - Data dictionary generation from extended properties
    """

    def __init__(
        self,
        output_base_dir: str = None,
        database_name: str = None,
        data_root: str = "./data",
        add_metadata_header: bool = True,
        overwrite_existing: bool = False,
        use_new_structure: bool = True,
    ):
        """
        Initialize hierarchical organizer.

        Args:
            output_base_dir: (Deprecated) Base directory for output. Use database_name instead.
            database_name: Database name for new hierarchical structure
            data_root: Root data directory (default: ./data)
            add_metadata_header: Add metadata headers to files
            overwrite_existing: Overwrite existing files
            use_new_structure: Use new hierarchical data structure (default: True)
        """
        self.add_metadata_header = add_metadata_header
        self.overwrite_existing = overwrite_existing
        self.use_new_structure = use_new_structure
        self.data_root = data_root
        self.database_name = database_name
        self.parser = EnhancedSQLParser()

        # Backward compatibility: support old output_base_dir parameter
        if output_base_dir:
            self.output_base_dir = Path(output_base_dir)
            self.use_new_structure = False
        else:
            self.output_base_dir = None

        # Statistics
        self.stats = {
            "files_processed": 0,
            "objects_separated": 0,
            "tables_with_constraints": 0,
            "indexed_views": 0,
            "by_type": {},
            "errors": [],
        }

    def organize_file(self, sql_file_path: str) -> Dict:
        """
        Organize a SQL file hierarchically.

        Args:
            sql_file_path: Path to SQL file

        Returns:
            Dictionary with organization results
        """
        print(f"\nProcessing: {sql_file_path}")

        sql_file_path = Path(sql_file_path)

        if not sql_file_path.exists():
            error_msg = f"File not found: {sql_file_path}"
            self.stats["errors"].append(error_msg)
            print(f"[ERROR] {error_msg}")
            return {}

        # Read file
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            error_msg = f"Error reading {sql_file_path}: {e}"
            self.stats["errors"].append(error_msg)
            print(f"[ERROR] {error_msg}")
            return {}

        # Parse using enhanced parser
        try:
            objects = self.parser.parse_file(content)
        except Exception as e:
            error_msg = f"Error parsing {sql_file_path}: {e}"
            self.stats["errors"].append(error_msg)
            print(f"[ERROR] {error_msg}")
            return {}

        if not objects:
            print(f"[WARN] No objects found in {sql_file_path}")
            return {}

        print(f"Found {len(objects)} object(s)")

        # Determine output directory
        if self.use_new_structure:
            # Use new hierarchical structure
            db_name = self.database_name or detect_database_name(sql_file_path)
            paths = DataPathManager(self.data_root, db_name)
            source_dir = paths.get_category_path("separated")
            print(f"Using database: {db_name}")
        else:
            # Use old structure (backward compatibility)
            source_folder_name = sql_file_path.stem
            source_dir = self.output_base_dir / source_folder_name
            source_dir.mkdir(parents=True, exist_ok=True)

        # Organize objects hierarchically
        created_files = {}

        # Filter out objects that should be grouped with parents
        standalone_objects = self._get_standalone_objects(objects)

        for obj in standalone_objects:

            files = self._save_object_hierarchically(
                obj, source_dir, sql_file_path.name
            )

            # Track created files
            for file_path in files:
                obj_type = obj.object_type.value
                if obj_type not in created_files:
                    created_files[obj_type] = []
                created_files[obj_type].append(file_path)

                self.stats["objects_separated"] += 1
                self.stats["by_type"][obj_type] = (
                    self.stats["by_type"].get(obj_type, 0) + 1
                )

        self.stats["files_processed"] += 1

        # Generate manifest
        self._generate_manifest(source_dir, created_files)

        return created_files

    def _get_standalone_objects(
        self, objects: List[SQLServerObject]
    ) -> List[SQLServerObject]:
        """
        Get objects that should be saved as standalone (not grouped with parent).

        Returns only top-level objects like tables, views, functions, procedures.
        Excludes constraints and indexes that belong to parent objects.
        """
        standalone = []

        for obj in objects:
            # If object has a parent and is a dependent type, skip it
            if obj.parent_object:
                if obj.object_type in [
                    SQLServerObjectType.INDEX,
                    SQLServerObjectType.CONSTRAINT,
                    SQLServerObjectType.FOREIGN_KEY,
                    SQLServerObjectType.CHECK_CONSTRAINT,
                    SQLServerObjectType.PRIMARY_KEY,
                ]:
                    # This object will be saved with its parent
                    continue

            # This is a standalone object
            standalone.append(obj)

        return standalone

    def _save_object_hierarchically(
        self, obj: SQLServerObject, source_dir: Path, source_file: str
    ) -> List[str]:
        """
        Save object and its related objects hierarchically.

        Args:
            obj: SQL Server object
            source_dir: Source directory
            source_file: Source file name

        Returns:
            List of created file paths
        """
        created_files = []

        # Determine object folder
        if obj.object_type == SQLServerObjectType.TABLE:
            type_folder = "tables"
        elif obj.object_type == SQLServerObjectType.VIEW:
            type_folder = "views"
        elif obj.object_type == SQLServerObjectType.FUNCTION:
            type_folder = "functions"
        elif obj.object_type == SQLServerObjectType.PROCEDURE:
            type_folder = "stored_procedures"
        elif obj.object_type == SQLServerObjectType.SCHEMA:
            type_folder = "schemas"
        elif obj.object_type == SQLServerObjectType.TYPE:
            type_folder = "types"
        else:
            type_folder = "other"

        # Create object-specific folder
        object_dir = source_dir / type_folder / obj.name
        object_dir.mkdir(parents=True, exist_ok=True)

        # Save main object
        main_file = object_dir / f"{obj.name}.sql"
        content = self._prepare_content(obj, source_file, is_main=True)
        self._write_file(main_file, content)
        created_files.append(str(main_file.relative_to(self.output_base_dir)))

        print(
            f"  [OK] {obj.object_type.value}: {obj.name} -> {main_file.relative_to(source_dir)}"
        )

        # Save related objects in subfolders
        if obj.indexes:
            idx_dir = object_dir / "indexes"
            idx_dir.mkdir(exist_ok=True)
            for idx in obj.indexes:
                idx_file = idx_dir / f"{idx.name}.sql"
                idx_content = self._prepare_content(
                    idx, source_file, parent_name=obj.name
                )
                self._write_file(idx_file, idx_content)
                created_files.append(str(idx_file.relative_to(self.output_base_dir)))
                print(f"    [OK] Index: {idx.name}")

        if obj.foreign_keys:
            fk_dir = object_dir / "foreign_keys"
            fk_dir.mkdir(exist_ok=True)
            for fk in obj.foreign_keys:
                fk_file = (
                    fk_dir
                    / f"{fk.name if hasattr(fk, 'name') and fk.name else 'FK'}.sql"
                )
                fk_content = self._prepare_content(
                    fk, source_file, parent_name=obj.name
                )
                self._write_file(fk_file, fk_content)
                created_files.append(str(fk_file.relative_to(self.output_base_dir)))

        if obj.check_constraints:
            chk_dir = object_dir / "check_constraints"
            chk_dir.mkdir(exist_ok=True)
            for chk in obj.check_constraints:
                chk_file = (
                    chk_dir
                    / f"{chk.name if hasattr(chk, 'name') and chk.name else 'CHK'}.sql"
                )
                chk_content = self._prepare_content(
                    chk, source_file, parent_name=obj.name
                )
                self._write_file(chk_file, chk_content)
                created_files.append(str(chk_file.relative_to(self.output_base_dir)))

        if obj.defaults:
            def_dir = object_dir / "defaults"
            def_dir.mkdir(exist_ok=True)
            for df in obj.defaults:
                df_file = (
                    def_dir
                    / f"{df.name if hasattr(df, 'name') and df.name else 'DF'}.sql"
                )
                df_content = self._prepare_content(
                    df, source_file, parent_name=obj.name
                )
                self._write_file(df_file, df_content)
                created_files.append(str(df_file.relative_to(self.output_base_dir)))

        if obj.constraints:
            con_dir = object_dir / "constraints"
            con_dir.mkdir(exist_ok=True)
            for con in obj.constraints:
                con_file = (
                    con_dir
                    / f"{con.name if hasattr(con, 'name') and con.name else 'CON'}.sql"
                )
                con_content = self._prepare_content(
                    con, source_file, parent_name=obj.name
                )
                self._write_file(con_file, con_content)
                created_files.append(str(con_file.relative_to(self.output_base_dir)))

        # Track special cases
        if obj.object_type == SQLServerObjectType.TABLE and (
            obj.indexes or obj.foreign_keys or obj.constraints
        ):
            self.stats["tables_with_constraints"] += 1

        if obj.object_type == SQLServerObjectType.VIEW and obj.indexes:
            self.stats["indexed_views"] += 1

        return created_files

    def _prepare_content(
        self,
        obj: SQLServerObject,
        source_file: str,
        is_main: bool = False,
        parent_name: str = None,
    ) -> str:
        """Prepare file content with metadata."""
        lines = []

        if self.add_metadata_header:
            lines.append("-- ============================================")
            lines.append(f"-- Object Type: {obj.object_type.value}")
            if is_main:
                lines.append(f"-- Object Name: {obj.full_name}")
            else:
                lines.append(
                    f"-- Constraint/Index Name: {getattr(obj, 'name', 'Unknown')}"
                )
                if parent_name:
                    lines.append(f"-- Parent Object: {parent_name}")
            lines.append(f"-- Source File: {source_file}")
            if obj.script_date:
                lines.append(f"-- Script Date: {obj.script_date}")
            lines.append(
                f"-- Separated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            lines.append("-- ============================================")
            lines.append("")

        lines.append(obj.sql_content.strip())

        if not obj.sql_content.strip().endswith("\n"):
            lines.append("")

        return "\n".join(lines)

    def _write_file(self, file_path: Path, content: str):
        """Write content to file."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            error_msg = f"Error writing {file_path}: {e}"
            self.stats["errors"].append(error_msg)
            print(f"  [ERROR] {error_msg}")

    def _generate_manifest(self, source_dir: Path, created_files: Dict):
        """Generate manifest file."""
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "source_directory": str(source_dir),
            "organization_type": "hierarchical",
            "statistics": {
                "objects_separated": self.stats["objects_separated"],
                "tables_with_constraints": self.stats["tables_with_constraints"],
                "indexed_views": self.stats["indexed_views"],
                "by_type": self.stats["by_type"],
            },
            "files_by_type": created_files,
        }

        manifest_path = source_dir / "organization_manifest.json"

        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            print(f"\n[OK] Manifest created: {manifest_path}")
        except Exception as e:
            print(f"[WARN] Could not create manifest: {e}")

    def print_summary(self):
        """Print organization summary."""
        print("\n" + "=" * 70)
        print("=== HIERARCHICAL ORGANIZATION SUMMARY ===")
        print("=" * 70)
        print(f"Files Processed:          {self.stats['files_processed']}")
        print(f"Objects Separated:        {self.stats['objects_separated']}")
        print(f"Tables with Constraints:  {self.stats['tables_with_constraints']}")
        print(f"Indexed Views:            {self.stats['indexed_views']}")

        print("\nBy Object Type:")
        for obj_type, count in self.stats["by_type"].items():
            if count > 0:
                print(f"  {obj_type:<20} {count:>3}")

        if self.stats["errors"]:
            print(f"\n[WARN] Errors: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:
                print(f"  - {error}")

        print(f"\n[OK] Output Directory: {self.output_base_dir}")
        print("=" * 70)


def organize_sql_hierarchically(
    input_file: str, output_dir: str = "./data/separated_sql"
) -> Dict:
    """
    Convenience function to organize SQL file hierarchically.

    Args:
        input_file: SQL file to organize
        output_dir: Output directory

    Returns:
        Organization results
    """
    organizer = HierarchicalOrganizer(
        output_base_dir=output_dir, add_metadata_header=True, overwrite_existing=True
    )

    results = organizer.organize_file(input_file)
    organizer.print_summary()

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "./data/separated_sql"

        print("Hierarchical SQL Organizer")
        print("=" * 70)
        print(f"Input:  {input_file}")
        print(f"Output: {output_dir}")
        print("=" * 70)

        organize_sql_hierarchically(input_file, output_dir)
    else:
        print("Usage: python hierarchical_organizer.py <sql_file> [output_dir]")
        print("\nExample:")
        print("  python hierarchical_organizer.py data/raw/AdventureWorksLT-All.sql")
