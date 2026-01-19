# Design: Parsed Objects API

## 1. Response Schema

### ParsedObject
```python
class ParsedObject(BaseModel):
    id: str                          # Unique ID, fallback to name
    name: str                        # Fully qualified (schema.object_name)
    object_type: Literal["FUNCTION", "TABLE", "VIEW", "TRIGGER", "SCHEMA", "MISC"]
    file_path: Optional[str]         # Relative path to chunk file
    definition: Optional[str]        # Full CREATE ... SQL
    columns: Optional[List[ColumnInfo]]  # For TABLE/VIEW
    run_id: str                      # Ingestion run identifier
    created_at: Optional[str]        # ISO-8601 timestamp
```

### ColumnInfo
```python
class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool = True
    is_primary: bool = False
    is_foreign: bool = False
    references: Optional[str] = None
```

### ObjectTypeGroup
```python
class ObjectTypeGroup(BaseModel):
    type: Literal["FUNCTION", "TABLE", "VIEW", "TRIGGER", "SCHEMA", "MISC"]
    count: int
    objects: List[ParsedObject]
```

### ParsedDatabase
```python
class ParsedDatabase(BaseModel):
    name: str                        # Logical database name
    source_file: Optional[str]       # Original source file
    run_id: str                      # Associated run
    object_types: List[ObjectTypeGroup]
```

### ParsedObjectsResponse
```python
class ParsedObjectsResponse(BaseModel):
    databases: List[ParsedDatabase]
```

### SimpleDependencyResponse
```python
class SimpleDependencyResponse(BaseModel):
    upstream: List[str]              # Object names that this depends on
    downstream: List[str]            # Object names that depend on this
```

## 2. Neo4j Query Strategy

### Fetching Objects with Grouping
```cypher
MATCH (n)
WHERE (n:Table OR n:View OR n:Function OR n:StoredProcedure OR n:FunctionOrProcedure OR n:Trigger)
  AND ($project_id IS NULL OR n.project_id = $project_id)
RETURN
    coalesce(n.database, n.source_file, 'default') as database,
    n.source_file as source_file,
    n.run_id as run_id,
    labels(n)[0] as label,
    n.id as id,
    n.name as name,
    n.file_path as file_path,
    n.definition as definition,
    n.columns as columns,
    n.created_at as created_at
ORDER BY database, label, n.name
```

### Type Mapping
```python
LABEL_TO_TYPE = {
    "Table": "TABLE",
    "View": "VIEW",
    "Function": "FUNCTION",
    "StoredProcedure": "FUNCTION",
    "FunctionOrProcedure": "FUNCTION",
    "Trigger": "TRIGGER",
    "Schema": "SCHEMA",
}
```

### Python Grouping Logic
```python
from collections import defaultdict

def group_objects(records: List[dict]) -> List[ParsedDatabase]:
    # Group by database
    db_map = defaultdict(lambda: {
        "source_file": None,
        "run_id": None,
        "type_map": defaultdict(list)
    })

    for record in records:
        db_name = record["database"] or "default"
        obj_type = LABEL_TO_TYPE.get(record["label"], "MISC")

        db_map[db_name]["source_file"] = record.get("source_file")
        db_map[db_name]["run_id"] = record.get("run_id")
        db_map[db_name]["type_map"][obj_type].append(
            ParsedObject(
                id=record.get("id") or record["name"],
                name=record["name"],
                object_type=obj_type,
                file_path=record.get("file_path"),
                definition=record.get("definition"),
                columns=parse_columns(record.get("columns")),
                run_id=record.get("run_id") or "",
                created_at=record.get("created_at"),
            )
        )

    # Build response
    databases = []
    for db_name, data in sorted(db_map.items()):
        object_types = [
            ObjectTypeGroup(
                type=obj_type,
                count=len(objects),
                objects=objects
            )
            for obj_type, objects in sorted(data["type_map"].items())
        ]
        databases.append(ParsedDatabase(
            name=db_name,
            source_file=data["source_file"],
            run_id=data["run_id"] or "",
            object_types=object_types
        ))

    return databases
```

## 3. Dependencies Query

### Simplified Response
The frontend expects just object names, not full metadata:

```cypher
MATCH (target)
WHERE target.name = $object_name
  AND (target.database = $database OR $database = '')
  AND ($project_id IS NULL OR target.project_id = $project_id)

// Upstream: what this object reads from
OPTIONAL MATCH (target)-[:READS_FROM|DERIVES|REFERENCES]->(upstream)

// Downstream: what reads from this object
OPTIONAL MATCH (downstream)-[:READS_FROM|DERIVES|REFERENCES]->(target)

RETURN
    collect(DISTINCT upstream.name) as upstream,
    collect(DISTINCT downstream.name) as downstream
```

## 4. Error Handling

- **Empty results**: Return `{ databases: [] }` or `{ upstream: [], downstream: [] }`
- **Missing object**: Return empty dependencies, not 404 (matches current graceful degradation)
- **Neo4j unavailable**: Return 503 Service Unavailable
- **Invalid parameters**: Return 400 Bad Request with error message

## 5. Backward Compatibility

The response format changes from flat to hierarchical. This is a **breaking change** but aligns with the frontend contract. The old flat format is not used by any known consumers.
