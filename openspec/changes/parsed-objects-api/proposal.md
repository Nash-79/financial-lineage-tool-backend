# Proposal: Expose Parsed Objects API

## Why

The frontend Database Explorer now presents a "Parsed Objects Explorer" UI that needs a structured, hierarchical view of parsed SQL artifacts (functions, tables, views, triggers, etc.) as well as object-level dependency information.

Today, the backend:
1. Parses SQL into Neo4j nodes during ingestion
2. Has basic `/api/v1/database/parsed-objects` and `/api/v1/database/objects/{db}/{name}/dependencies` endpoints
3. But returns a **flat list** instead of the **hierarchical structure** the frontend expects

The frontend's `useParsedObjects` hook expects data grouped by: `database → objectType → objects`. The current implementation returns `{ total, objects: [...] }` which breaks the frontend tree view.

## What Changes

### 1. Refactor `GET /api/v1/database/parsed-objects`

**Current Response (broken):**
```json
{
  "total": 5,
  "objects": [
    { "name": "fn1", "type": "Function", "database": "db1", ... }
  ]
}
```

**New Response (frontend-compatible):**
```json
{
  "databases": [
    {
      "name": "postgres_investments",
      "source_file": "postgres_investments.sql",
      "run_id": "20260113_181024_001",
      "object_types": [
        {
          "type": "FUNCTION",
          "count": 3,
          "objects": [
            {
              "id": "fn1",
              "name": "stg_investments.load_instrument_dim",
              "object_type": "FUNCTION",
              "file_path": "chunks/postgres_investments/FUNCTION/load_instrument_dim.sql",
              "definition": "CREATE OR REPLACE FUNCTION ...",
              "columns": null,
              "run_id": "20260113_181024_001",
              "created_at": "2026-01-13T18:10:24Z"
            }
          ]
        }
      ]
    }
  ]
}
```

**New Query Parameters:**
- `project_id` (optional): Scope results to a specific project
- `repo_ids` (optional): Comma-separated repository IDs for filtering

### 2. Simplify `GET /api/v1/database/objects/{db}/{name}/dependencies`

**Current Response:**
```json
{
  "object_name": "fn1",
  "database": "db1",
  "upstream": [{ "name": "t1", "type": "Table", ... }],
  "downstream": [{ "name": "v1", "type": "View", ... }]
}
```

**New Response (frontend-compatible):**
```json
{
  "upstream": ["stg_investments.transactions", "public.funds"],
  "downstream": ["reporting.v_portfolio_summary"]
}
```

The frontend expects simple string arrays, not complex objects.

**New Query Parameters:**
- `project_id` (optional): Scope to project
- `repo_ids` (optional): Comma-separated repository IDs

### 3. Data Model Requirements

Objects returned must include these fields:
- `id`: Unique identifier (fallback to `name` if missing)
- `name`: Fully qualified name (e.g., `schema.function_name`)
- `object_type`: One of `FUNCTION`, `TABLE`, `VIEW`, `TRIGGER`, `SCHEMA`, `MISC`
- `file_path`: Relative path to source chunk file
- `definition`: Full SQL body (for preview)
- `columns`: Array of column metadata (for TABLE/VIEW)
- `run_id`: Ingestion run identifier
- `created_at`: ISO-8601 timestamp

### 4. Grouping Logic

The backend must:
1. Query all parsed objects from Neo4j
2. Group by `database` (derived from source file or schema prefix)
3. Within each database, group by `object_type`
4. Map raw labels to canonical types: `Function`→`FUNCTION`, `Table`→`TABLE`, etc.

## Acceptance Criteria

- [ ] `/api/v1/database/parsed-objects` returns hierarchical `{ databases: [...] }` structure
- [ ] Objects include `id`, `definition`, `file_path`, `run_id`, `created_at` fields
- [ ] Both endpoints support `project_id` query parameter
- [ ] `/api/v1/database/objects/{db}/{name}/dependencies` returns `{ upstream: string[], downstream: string[] }`
- [ ] Empty results return empty arrays, not errors
- [ ] Frontend `useParsedObjects` hook works without modification
