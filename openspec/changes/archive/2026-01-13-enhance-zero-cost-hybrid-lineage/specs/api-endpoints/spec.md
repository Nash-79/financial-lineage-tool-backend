# api-endpoints Spec Deltas

## ADDED Requirements

### Requirement: SQL Dialect Discovery Endpoint
The system SHALL expose an endpoint for discovering available SQL dialects to enable dynamic frontend configuration.

#### Scenario: List available dialects
- **WHEN** client requests `GET /api/v1/config/sql-dialects`
- **THEN** the system returns a JSON array of dialect objects
- **AND** each object includes:
  - `id`: Dialect identifier (e.g., "tsql", "postgres")
  - `display_name`: Human-readable name (e.g., "SQL Server (T-SQL)")
  - `sqlglot_key`: Key to pass to sqlglot's `read` parameter
  - `is_default`: Boolean flag for default selection
  - `enabled`: Boolean flag for availability
- **AND** response status is 200 OK

#### Scenario: Dialect list example
- **WHEN** system has multiple dialects configured
- **THEN** response might include:
  ```json
  [
    {
      "id": "duckdb",
      "display_name": "DuckDB",
      "sqlglot_key": "duckdb",
      "is_default": true,
      "enabled": true
    },
    {
      "id": "tsql",
      "display_name": "SQL Server (T-SQL)",
      "sqlglot_key": "tsql",
      "is_default": false,
      "enabled": true
    },
    {
      "id": "fabric",
      "display_name": "Microsoft Fabric",
      "sqlglot_key": "tsql",
      "is_default": false,
      "enabled": true
    }
  ]
  ```

#### Scenario: Empty dialect registry
- **WHEN** no dialects are configured (edge case)
- **THEN** response returns empty array `[]`
- **AND** status code is still 200 OK

#### Scenario: Frontend integration
- **WHEN** frontend loads file upload or ingestion settings page
- **THEN** it queries `/api/v1/config/sql-dialects` on component mount
- **AND** populates dropdown with available dialects
- **AND** pre-selects the default dialect
- **AND** sends selected `sql_dialect` with ingestion API calls

### Requirement: Project Link Endpoints
The system SHALL expose endpoints for creating, listing, and deleting project-to-project links.

#### Scenario: Create project link
- **WHEN** client sends `POST /api/v1/projects/{project_id}/project-links`
- **AND** payload includes `target_project_id`
- **THEN** system creates a project link with `link_type="manual"`
- **AND** returns the created link metadata

#### Scenario: List project links
- **WHEN** client sends `GET /api/v1/projects/{project_id}/project-links`
- **THEN** response returns an array of project link records
- **AND** each record includes source/target project IDs and link metadata

#### Scenario: Delete project link
- **WHEN** client sends `DELETE /api/v1/projects/{project_id}/project-links/{link_id}`
- **THEN** system deletes the link if it involves the project
- **AND** response status is 204 No Content

## MODIFIED Requirements

### Requirement: Ingestion Endpoints
The system SHALL provide endpoints for data ingestion and accept a SQL dialect parameter for SQL-based ingestion.

#### Scenario: Ingest SQL file with dialect
- **WHEN** frontend sends POST to /api/v1/ingest with file path
- **THEN** system ingests SQL file asynchronously
- **AND** request payload includes `dialect` field (string) or uses default when omitted
- **AND** backend validates dialect against registry
- **AND** returns 400 Bad Request if dialect is unknown or disabled
- **AND** returns {"status": "accepted", "file": "path", "project_id": "...", "run_id": "...", "ingestion_id": "...", "run_dir": "..."}
- **AND** file is chunked, embedded, and indexed
- **AND** progress can be tracked via activity endpoint

#### Scenario: Ingest raw SQL with dialect
- **WHEN** frontend sends POST to /api/v1/ingest/sql with SQL content
- **THEN** system parses and ingests SQL directly
- **AND** request payload includes `dialect` field (string) or uses default when omitted
- **AND** backend validates dialect against registry
- **AND** returns 400 Bad Request if dialect is unknown or disabled
- **AND** extracts entities and relationships
- **AND** adds to knowledge graph
- **AND** returns {"status": "success", "source": "name"}

#### Scenario: Repository ingestion with dialect
- **WHEN** client ingests repository via `POST /api/v1/github/ingest`
- **THEN** request includes `dialect` field in configuration
- **AND** dialect is applied to all `.sql` files in repository
- **AND** same validation rules apply

#### Scenario: Auto-detect dialect (optional)
- **WHEN** client sends `dialect: "auto"`
- **THEN** backend attempts heuristic dialect detection
- **AND** this mode is best-effort and not guaranteed
- **AND** falls back to default dialect if detection fails

#### Scenario: Dialect validation error
- **WHEN** unknown dialect is provided (e.g., "oracle")
- **THEN** response status is 400 Bad Request
- **AND** error message lists available dialects
- **AND** error includes suggestion to check `/api/v1/config/sql-dialects`
