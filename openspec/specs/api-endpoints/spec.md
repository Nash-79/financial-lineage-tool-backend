# api-endpoints Specification

## Purpose
TBD - created by archiving change dockerize-backend-with-huggingface. Update Purpose after archive.
## Requirements
### Requirement: Chat Endpoints
The system SHALL provide multiple chat endpoints for different query types with proper error handling

#### Scenario: Chat endpoint error handling
- **WHEN** chat endpoint encounters LLM error
- **THEN** endpoint returns 500 with descriptive error message
- **AND** error details include which component failed
- **AND** error is logged with full stack trace
- **AND** user receives actionable error message

#### Scenario: Chat endpoint model configuration
- **WHEN** chat endpoint calls Ollama generate
- **THEN** call includes model parameter from config.LLM_MODEL
- **AND** model parameter is required and validated
- **AND** missing model parameter causes clear error
- **AND** unsupported model name returns helpful error

### Requirement: Lineage Endpoints
The system SHALL provide endpoints for lineage visualization and search.

#### Scenario: Get lineage nodes
- **WHEN** frontend sends GET to /api/lineage/nodes
- **THEN** system returns all nodes in knowledge graph
- **AND** nodes include id, label, type, and metadata
- **AND** response is paginated if needed

#### Scenario: Get lineage edges
- **WHEN** frontend sends GET to /api/lineage/edges
- **THEN** system returns all relationships between nodes
- **AND** edges include source, target, and relationship type
- **AND** response format matches visualization library requirements

#### Scenario: Search lineage
- **WHEN** frontend sends GET to /api/lineage/search with query parameter
- **THEN** system searches nodes and edges by name/properties
- **AND** returns matching nodes and related edges
- **AND** results are ranked by relevance

#### Scenario: Get node lineage
- **WHEN** frontend sends GET to /api/lineage/node/{node_id}
- **THEN** system returns upstream and downstream lineage for node
- **AND** response includes nodes and edges in lineage path
- **AND** supports direction parameter (upstream/downstream/both)

### Requirement: Data Endpoints
The system SHALL provide endpoints for data and file management.

#### Scenario: Get recent files
- **WHEN** frontend sends GET to /api/files/recent
- **THEN** system returns recently processed files
- **AND** includes file metadata (name, size, status, timestamp)
- **AND** sorted by processing time (newest first)
- **AND** limited to last 50 files

#### Scenario: Get file list
- **WHEN** frontend sends GET to /api/files
- **THEN** system returns all ingested files
- **AND** includes processing status and statistics
- **AND** supports pagination and filtering

#### Scenario: Search files
- **WHEN** frontend sends GET to /api/files/search with query
- **THEN** system searches files by name or path
- **AND** returns matching files with metadata
- **AND** results are sorted by relevance

#### Scenario: Get file statistics
- **WHEN** frontend sends GET to /api/files/stats
- **THEN** system returns file processing statistics
- **AND** includes total, processed, pending, error counts
- **AND** includes storage usage metrics

#### Scenario: Get dashboard statistics
- **WHEN** frontend sends GET to /api/stats
- **THEN** system returns overall system statistics
- **AND** includes node count, file count, query count
- **AND** includes recent activity trends
- **AND** formatted for dashboard display

#### Scenario: Get database schemas
- **WHEN** frontend sends GET to /api/database/schemas
- **THEN** system returns list of discovered database schemas
- **AND** includes schema metadata (tables, views, procedures)
- **AND** includes last updated timestamp

### Requirement: Activity and Monitoring Endpoints
The system SHALL provide endpoints for activity tracking with reliable persistence

#### Scenario: Activity event persistence
- **WHEN** system activity occurs (ingestion, query, error)
- **THEN** activity event is persisted to storage
- **AND** persistence callback is async callable function
- **AND** persistence failures are logged but don't block operations
- **AND** failed events are retried or queued

#### Scenario: Activity tracker initialization
- **WHEN** middleware initializes activity tracker
- **THEN** tracker receives valid callable for persistence
- **AND** callable accepts event data as parameter
- **AND** callable returns success/failure status
- **AND** initialization errors fail startup with clear message

### Requirement: Health and Admin Endpoints
The system SHALL provide health check and administrative endpoints.

#### Scenario: Health check
- **WHEN** frontend sends GET to /health
- **THEN** system returns service health status
- **AND** checks Ollama, Qdrant, Neo4j, Redis connectivity
- **AND** returns 200 if healthy, 503 if degraded
- **AND** includes detailed status for each service

#### Scenario: Admin restart
- **WHEN** authenticated admin sends POST to /admin/restart
- **THEN** system triggers graceful container restart
- **AND** returns {"status": "restarting"}
- **AND** Docker restart policy brings container back up
- **AND** unauthenticated requests return 403

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

### Requirement: Endpoint Configuration
The system SHALL support configurable API endpoint paths.

#### Scenario: Custom endpoint paths
- **WHEN** system reads API_ENDPOINTS configuration
- **THEN** it allows customization of endpoint paths
- **AND** maintains backward compatibility
- **AND** logs endpoint registration on startup

#### Scenario: Endpoint path validation
- **WHEN** endpoints are registered
- **THEN** system validates no path conflicts exist
- **AND** logs all registered endpoints
- **AND** provides clear error if conflicts found

### Requirement: CORS and Security
The system SHALL configure CORS and security for all endpoints.

#### Scenario: CORS configuration
- **WHEN** frontend makes cross-origin request
- **THEN** CORS headers allow frontend origin
- **AND** supports credentials if needed
- **AND** allows required HTTP methods

#### Scenario: Rate limiting
- **WHEN** client exceeds rate limit
- **THEN** system returns 429 Too Many Requests
- **AND** includes Retry-After header
- **AND** admin endpoints have stricter limits

### Requirement: Pydantic Model Validation
API models SHALL be fully defined without forward reference errors

#### Scenario: OpenAPI schema generation
- **WHEN** FastAPI generates OpenAPI schema at startup
- **THEN** all Pydantic models are fully resolved
- **AND** no forward reference errors occur
- **AND** schema generation completes without warnings
- **AND** /docs endpoint renders successfully

#### Scenario: Type annotation imports
- **WHEN** API model uses Dict, List, Any types
- **THEN** types are imported explicitly from typing module
- **AND** no forward references to undefined types
- **AND** Annotated types are properly configured
- **AND** all referenced models are defined before use

#### Scenario: Model rebuilding
- **WHEN** Pydantic model uses forward references
- **THEN** model calls .model_rebuild() after all types defined
- **AND** rebuild completes without errors
- **AND** rebuilt model validates correctly
- **AND** OpenAPI schema includes rebuilt model

### Requirement: Admin Restart Endpoint
System SHALL provide endpoint to trigger graceful container restart

#### Scenario: Admin restart request
- **WHEN** frontend sends POST to /admin/restart
- **THEN** endpoint returns 200 with {"status": "restarting"}
- **AND** endpoint triggers Docker container restart
- **AND** Docker restart policy brings container back up
- **AND** response is sent before restart begins

#### Scenario: Restart endpoint availability
- **WHEN** frontend checks if restart endpoint exists
- **THEN** OPTIONS /admin/restart returns 200 or 204
- **AND** endpoint appears in OpenAPI docs
- **AND** endpoint is registered in FastAPI routes
- **AND** endpoint path matches frontend expectations

#### Scenario: Restart graceful shutdown
- **WHEN** restart is triggered
- **THEN** system closes active connections gracefully
- **AND** system waits for in-flight requests to complete
- **AND** system persists any pending activity events
- **AND** system exits with code 0 for Docker restart

### Requirement: API Error Responses
All endpoints SHALL return consistent error response format

#### Scenario: Standard error response
- **WHEN** endpoint encounters error
- **THEN** response contains "detail" field with error message
- **AND** response includes appropriate HTTP status code
- **AND** 500 errors include component that failed
- **AND** 400 errors include validation details

#### Scenario: Error logging
- **WHEN** endpoint returns error response
- **THEN** error is logged with request context
- **AND** log includes endpoint path and method
- **AND** log includes error type and message
- **AND** 500 errors include stack trace in logs

#### Scenario: Service unavailable errors
- **WHEN** backend service is unavailable (Ollama, Neo4j, Qdrant)
- **THEN** endpoint returns 503 Service Unavailable
- **AND** error message indicates which service is down
- **AND** error message includes troubleshooting hints
- **AND** health check endpoint reflects service status

### Requirement: WebSocket Configuration Endpoint

System MUST provide an endpoint that returns the WebSocket URL for frontend clients.

#### Scenario: Retrieving WebSocket configuration

- **WHEN** frontend requests WebSocket configuration
- **THEN** backend returns GET /api/v1/config/websocket endpoint
- **AND** response includes WebSocket URL as string
- **AND** response status is 200 OK

#### Scenario: Environment-specific WebSocket URL

- **WHEN** application runs in different environments (local, staging, production)
- **THEN** WebSocket URL MUST reflect the current environment
- **AND** URL MUST be configurable via environment variable
- **AND** default value for local development is ws://127.0.0.1:8000/admin/ws/dashboard

#### Scenario: Frontend discovers WebSocket URL dynamically

- **WHEN** frontend application initializes
- **THEN** frontend MUST call /api/v1/config/websocket to get WebSocket URL
- **AND** frontend uses returned URL for WebSocket connections
- **AND** frontend does not hardcode WebSocket URL

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

