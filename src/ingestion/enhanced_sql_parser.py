"""
Enhanced SQL Parser - Uses SQL Server comment patterns for object detection.

This parser detects SQL Server object boundaries using the standard comment format:
/****** Object:  Table [Schema].[Name]    Script Date: ... ******/

It groups related objects together:
- Tables with their constraints, indexes, defaults
- Views with their indexes (for indexed views)
- Extended properties for data dictionary
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum


class SQLServerObjectType(str, Enum):
    """SQL Server object types from comment headers."""

    TABLE = "Table"
    VIEW = "View"
    FUNCTION = "UserDefinedFunction"
    PROCEDURE = "StoredProcedure"
    INDEX = "Index"
    CONSTRAINT = "Default"
    FOREIGN_KEY = "ForeignKey"
    CHECK_CONSTRAINT = "Check"
    PRIMARY_KEY = "PrimaryKey"
    TRIGGER = "Trigger"
    SCHEMA = "Schema"
    TYPE = "UserDefinedType"
    XML_SCHEMA = "XmlSchemaCollection"
    UNKNOWN = "Unknown"


@dataclass
class SQLServerObject:
    """Represents a SQL Server database object."""

    object_type: SQLServerObjectType
    schema: str
    name: str
    full_name: str  # [Schema].[Name]
    sql_content: str
    start_line: int = 0
    end_line: int = 0
    parent_object: Optional[str] = (
        None  # For constraints/indexes, the table/view they belong to
    )
    script_date: Optional[str] = None

    # Related objects (for hierarchical grouping)
    constraints: List["SQLServerObject"] = field(default_factory=list)
    indexes: List["SQLServerObject"] = field(default_factory=list)
    defaults: List["SQLServerObject"] = field(default_factory=list)
    foreign_keys: List["SQLServerObject"] = field(default_factory=list)
    check_constraints: List["SQLServerObject"] = field(default_factory=list)
    extended_properties: List[Dict] = field(default_factory=list)


class EnhancedSQLParser:
    """
    Enhanced SQL parser that uses SQL Server comment patterns.

    Detects object boundaries using /****** Object: ... ******/ comments
    and groups related objects hierarchically.
    """

    # Pattern for SQL Server object comments
    OBJECT_COMMENT_PATTERN = re.compile(
        r"/\*{6}\s+Object:\s+(\w+)\s+(\[[\w\.\[\]]+\])\s+Script Date:([^\*]+)\*{6}/",
        re.IGNORECASE,
    )

    # Pattern for GO statements (batch separator)
    GO_PATTERN = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)

    # Pattern for ALTER TABLE ... ADD CONSTRAINT
    ALTER_CONSTRAINT_PATTERN = re.compile(
        r"ALTER\s+TABLE\s+(\[[\w\.\[\]]+\])\s+ADD\s+CONSTRAINT\s+(\[[\w\.\[\]]+\])",
        re.IGNORECASE,
    )

    # Pattern for ALTER TABLE ... ADD (defaults)
    ALTER_DEFAULT_PATTERN = re.compile(
        r"ALTER\s+TABLE\s+(\[[\w\.\[\]]+\])\s+ADD\s+CONSTRAINT\s+(\[[\w\.\[\]]+\])\s+DEFAULT",
        re.IGNORECASE,
    )

    # Pattern for foreign keys
    FOREIGN_KEY_PATTERN = re.compile(
        r"ALTER\s+TABLE\s+(\[[\w\.\[\]]+\])\s+(?:WITH\s+CHECK\s+)?ADD\s+CONSTRAINT\s+(\[[\w\.\[\]]+\])\s+FOREIGN\s+KEY",
        re.IGNORECASE,
    )

    # Pattern for check constraints
    CHECK_CONSTRAINT_PATTERN = re.compile(
        r"ALTER\s+TABLE\s+(\[[\w\.\[\]]+\])\s+(?:WITH\s+CHECK\s+)?ADD\s+CONSTRAINT\s+(\[[\w\.\[\]]+\])\s+CHECK",
        re.IGNORECASE,
    )

    # Pattern for extended properties
    EXTENDED_PROPERTY_PATTERN = re.compile(
        r"EXEC\s+sys\.sp_addextendedproperty\s+@name=N'(\w+)',\s+@value=N'([^']*)'",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, dialect: str = "tsql", cache=None):
        self.dialect = dialect
        self.objects = []
        self.object_map = {}  # Map of object name to SQLServerObject
        self.cache = cache  # Optional ParseCache instance

    def parse_file_from_path(self, file_path: str) -> List[SQLServerObject]:
        """
        Parse SQL file from path with optional caching support.

        Args:
            file_path: Path to SQL file

        Returns:
            List of parsed SQL Server objects
        """
        # Try cache first if available
        if self.cache:
            cached_result = self.cache.get(file_path)
            if cached_result is not None:
                # Restore parser state from cache
                self.objects = cached_result["objects"]
                self.object_map = cached_result["object_map"]
                return self.objects

        # Cache miss or no cache - parse file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = self.parse_file(content)

        # Store in cache if available
        if self.cache:
            cache_data = {"objects": self.objects, "object_map": self.object_map}
            self.cache.set(file_path, cache_data)

        return result

    def parse_file(self, content: str) -> List[SQLServerObject]:
        """
        Parse SQL file using comment-based object detection.

        Args:
            content: SQL file content

        Returns:
            List of parsed SQL Server objects
        """
        self.objects = []
        self.object_map = {}

        # Split by object comments
        object_chunks = self._split_by_object_comments(content)

        # Parse each chunk
        for chunk in object_chunks:
            obj = self._parse_object_chunk(chunk)
            if obj:
                self.objects.append(obj)
                self.object_map[obj.full_name] = obj

        # Group related objects hierarchically
        self._group_related_objects()

        return self.objects

    def _split_by_object_comments(self, content: str) -> List[Dict]:
        """Split content by /****** Object: ... ******/ comments."""
        chunks = []
        lines = content.split("\n")

        current_chunk = {
            "header": None,
            "object_type": None,
            "object_name": None,
            "script_date": None,
            "content_lines": [],
            "start_line": 0,
        }

        line_num = 0

        for line in lines:
            line_num += 1

            # Check if this is an object comment
            match = self.OBJECT_COMMENT_PATTERN.search(line)

            if match:
                # Save previous chunk if it has content
                if current_chunk["content_lines"]:
                    chunks.append(current_chunk)

                # Start new chunk
                current_chunk = {
                    "header": match.group(0),
                    "object_type": match.group(1).strip(),
                    "object_name": match.group(2).strip(),
                    "script_date": match.group(3).strip(),
                    "content_lines": [],
                    "start_line": line_num,
                }
            else:
                current_chunk["content_lines"].append(line)

        # Add last chunk
        if current_chunk["content_lines"]:
            chunks.append(current_chunk)

        return chunks

    def _parse_object_chunk(self, chunk: Dict) -> Optional[SQLServerObject]:
        """Parse a single object chunk."""
        if not chunk.get("object_name"):
            # No object header - might be orphan SQL
            return None

        object_type = self._map_object_type(chunk["object_type"])
        full_name = chunk["object_name"]

        # Extract schema and name
        schema, name = self._parse_full_name(full_name)

        # Get SQL content
        sql_content = "\n".join(chunk["content_lines"])

        # Detect parent object for constraints/indexes
        parent_object = self._detect_parent_object(sql_content, object_type)

        return SQLServerObject(
            object_type=object_type,
            schema=schema,
            name=name,
            full_name=full_name,
            sql_content=sql_content,
            start_line=chunk["start_line"],
            parent_object=parent_object,
            script_date=chunk.get("script_date"),
        )

    def _map_object_type(self, type_str: str) -> SQLServerObjectType:
        """Map SQL Server object type string to enum."""
        type_mapping = {
            "table": SQLServerObjectType.TABLE,
            "view": SQLServerObjectType.VIEW,
            "storedprocedure": SQLServerObjectType.PROCEDURE,
            "userdefinedfunction": SQLServerObjectType.FUNCTION,
            "index": SQLServerObjectType.INDEX,
            "default": SQLServerObjectType.CONSTRAINT,
            "foreignkey": SQLServerObjectType.FOREIGN_KEY,
            "check": SQLServerObjectType.CHECK_CONSTRAINT,
            "primarykey": SQLServerObjectType.PRIMARY_KEY,
            "trigger": SQLServerObjectType.TRIGGER,
            "schema": SQLServerObjectType.SCHEMA,
            "userdefinedtype": SQLServerObjectType.TYPE,
            "xmlschemacollection": SQLServerObjectType.XML_SCHEMA,
        }

        key = type_str.lower().replace("_", "").replace(" ", "")
        return type_mapping.get(key, SQLServerObjectType.UNKNOWN)

    def _parse_full_name(self, full_name: str) -> tuple:
        """Parse [Schema].[Name] into schema and name."""
        # Remove brackets
        clean_name = full_name.replace("[", "").replace("]", "")

        parts = clean_name.split(".")
        if len(parts) == 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            return "dbo", parts[0]
        else:
            # Handle [Database].[Schema].[Name]
            return parts[-2], parts[-1]

    def _detect_parent_object(
        self, sql_content: str, object_type: SQLServerObjectType
    ) -> Optional[str]:
        """Detect parent object for constraints and indexes."""
        if object_type == SQLServerObjectType.INDEX:
            # Look for CREATE INDEX ... ON [Table] or CREATE INDEX ... ON [Schema].[Table]
            match = re.search(
                r"CREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\s+\[?\w+\]?\s+ON\s+(\[[^\]]+\]\.\[[^\]]+\]|\[[^\]]+\])",
                sql_content,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

        # Check for ALTER TABLE statements
        alter_match = self.ALTER_CONSTRAINT_PATTERN.search(sql_content)
        if alter_match:
            return alter_match.group(1)

        # Check for foreign keys
        fk_match = self.FOREIGN_KEY_PATTERN.search(sql_content)
        if fk_match:
            return fk_match.group(1)

        # Check for check constraints
        check_match = self.CHECK_CONSTRAINT_PATTERN.search(sql_content)
        if check_match:
            return check_match.group(1)

        return None

    def _group_related_objects(self):
        """Group constraints, indexes, etc. with their parent tables/views."""
        for obj in self.objects:
            # Try to find parent object
            parent = None

            if obj.parent_object:
                # Direct match
                if obj.parent_object in self.object_map:
                    parent = self.object_map[obj.parent_object]
                else:
                    # Try to match by name only (without schema)
                    parent_name = (
                        obj.parent_object.replace("[", "")
                        .replace("]", "")
                        .split(".")[-1]
                    )
                    for full_name, parent_obj in self.object_map.items():
                        if parent_obj.name == parent_name:
                            parent = parent_obj
                            break

            if parent:
                # Group by object type
                if "FOREIGN" in obj.sql_content.upper():
                    parent.foreign_keys.append(obj)
                elif (
                    "CHECK" in obj.sql_content.upper()
                    and "CONSTRAINT" in obj.sql_content.upper()
                ):
                    parent.check_constraints.append(obj)
                elif "DEFAULT" in obj.sql_content.upper():
                    parent.defaults.append(obj)
                elif obj.object_type == SQLServerObjectType.INDEX:
                    parent.indexes.append(obj)
                else:
                    parent.constraints.append(obj)

    def parse_extended_properties(self, content: str) -> Dict[str, List[Dict]]:
        """
        Parse extended properties for data dictionary.

        Returns:
            Dictionary mapping object names to their properties
        """
        properties_map = {}

        # Find all sp_addextendedproperty calls
        for match in self.EXTENDED_PROPERTY_PATTERN.finditer(content):
            prop_name = match.group(1)
            prop_value = match.group(2)

            # Extract object information from the EXEC statement
            # This is simplified - full implementation would parse all parameters
            properties_map.setdefault("global", []).append(
                {"name": prop_name, "value": prop_value}
            )

        return properties_map

    def get_objects_by_type(
        self, object_type: SQLServerObjectType
    ) -> List[SQLServerObject]:
        """Get all objects of a specific type."""
        return [obj for obj in self.objects if obj.object_type == object_type]

    def get_tables_with_dependencies(self) -> List[SQLServerObject]:
        """Get all tables with their constraints and indexes."""
        return [
            obj for obj in self.objects if obj.object_type == SQLServerObjectType.TABLE
        ]

    def get_indexed_views(self) -> List[SQLServerObject]:
        """Get views that have indexes (indexed views)."""
        return [
            obj
            for obj in self.objects
            if obj.object_type == SQLServerObjectType.VIEW and len(obj.indexes) > 0
        ]


def parse_sql_with_comments(
    content: str, dialect: str = "tsql"
) -> List[SQLServerObject]:
    """
    Convenience function to parse SQL using comment-based detection.

    Args:
        content: SQL file content
        dialect: SQL dialect (default: tsql)

    Returns:
        List of parsed SQL Server objects
    """
    parser = EnhancedSQLParser(dialect=dialect)
    return parser.parse_file(content)


if __name__ == "__main__":
    # Test with sample SQL
    test_sql = """
/****** Object:  Table [SalesLT].[ProductCategory]    Script Date: 4/7/2021 10:02:56 AM ******/
CREATE TABLE [SalesLT].[ProductCategory](
    [ProductCategoryID] [int] IDENTITY(1,1) NOT NULL,
    [Name] [dbo].[Name] NOT NULL
) ON [PRIMARY]
GO

/****** Object:  Index [PK_ProductCategory]    Script Date: 4/7/2021 10:02:56 AM ******/
CREATE CLUSTERED INDEX [PK_ProductCategory] ON [SalesLT].[ProductCategory]
(
    [ProductCategoryID] ASC
)
GO

ALTER TABLE [SalesLT].[ProductCategory] ADD  CONSTRAINT [DF_ProductCategory_rowguid]  DEFAULT (newid()) FOR [rowguid]
GO

ALTER TABLE [SalesLT].[ProductCategory]  WITH CHECK ADD  CONSTRAINT [FK_ProductCategory_Parent]
FOREIGN KEY([ParentProductCategoryID])
REFERENCES [SalesLT].[ProductCategory] ([ProductCategoryID])
GO
    """

    parser = EnhancedSQLParser()
    objects = parser.parse_file(test_sql)

    print(f"Found {len(objects)} objects:")
    for obj in objects:
        print(f"  {obj.object_type.value}: {obj.full_name}")
        if obj.parent_object:
            print(f"    Parent: {obj.parent_object}")

    # Show tables with dependencies
    tables = parser.get_tables_with_dependencies()
    for table in tables:
        print(f"\nTable: {table.full_name}")
        print(f"  Indexes: {len(table.indexes)}")
        print(f"  Foreign Keys: {len(table.foreign_keys)}")
        print(f"  Defaults: {len(table.defaults)}")
        print(f"  Check Constraints: {len(table.check_constraints)}")
