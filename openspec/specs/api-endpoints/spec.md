# api-endpoints Specification

## Purpose
TBD - created by archiving change dockerize-backend-with-huggingface. Update Purpose after archive.
## Requirements
### Requirement: Chat Endpoints
The system SHALL provide multiple chat endpoints for different query types with proper error handling and optional memory context.

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

#### Scenario: Chat request with session memory
- **WHEN** client sends chat request with session_id
- **THEN** system retrieves relevant memory context from vector store
- **AND** memory context is prepended to query context
- **AND** memory retrieval runs in parallel with other operations

#### Scenario: Chat request without memory
- **WHEN** client sends chat request with skip_memory=true
- **THEN** system bypasses memory context retrieval
- **AND** saves ~300ms latency
- **AND** query proceeds with empty memory context

#### Scenario: Chat response with graph visualization
- **WHEN** deep analysis finds graph entities
- **THEN** response includes graph_data field
- **AND** graph_data contains nodes and edges arrays
- **AND** nodes include id, label, and type
- **AND** edges include source, target, and relationship type

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

### Requirement: Frontend SHALL use correct backend API routes
The system SHALL configure frontend API calls to match backend routes and handle secured endpoints.

#### Scenario: Lineage endpoints use /api/v1
- **WHEN** the frontend fetches lineage nodes/search/node lineage
- **THEN** it calls `/api/v1/lineage/nodes`, `/api/v1/lineage/edges`, `/api/v1/lineage/search`, `/api/v1/lineage/node/{id}`
- **AND** endpoints are configurable via Settings
- **AND** requests return live data instead of mock fallbacks

#### Scenario: Upload endpoint is configurable
- **WHEN** the frontend uploads files
- **THEN** it uses the configured upload endpoint from Settings (default `/api/v1/files/upload`)
- **AND** respects allowed extensions and size from backend config before sending

#### Scenario: Restart endpoint respects auth/flags
- **WHEN** the frontend tests or triggers `/admin/restart`
- **THEN** it includes configured auth headers/tokens if required
- **AND** handles 401/403/404/disabled responses gracefully without retry loops
- **AND** hides or disables restart controls when backend reports it as restricted

### Requirement: File metadata endpoints are backed by DuckDB
The system SHALL return real file metadata from DuckDB for file list, search, and stats endpoints.

#### Scenario: List files from metadata store
- **WHEN** frontend requests `GET /api/v1/files`
- **THEN** the system returns files derived from DuckDB runs/files tables
- **AND** each record includes `id`, `filename`, `relative_path`, `file_type`, `source`, `run_id`, `project_id`, `repository_id`, `status`, and timestamps
- **AND** results support pagination and filtering by project, repository, and source

#### Scenario: File stats and search
- **WHEN** frontend requests `GET /api/v1/files/stats`
- **THEN** the system returns counts derived from DuckDB (total, processed, pending, errors, skipped)
- **AND** counts reflect the latest run statuses
- **WHEN** frontend requests `GET /api/v1/files/search?q=...`
- **THEN** the system returns matching files from DuckDB by filename or relative_path
- **AND** results are ordered by relevance and recency

### Requirement: Upload and GitHub ingestion share the indexing pipeline
The system SHALL apply the same chunking, embedding, and indexing pipeline to files ingested via upload and GitHub endpoints.

#### Scenario: Upload ingestion indexes code chunks
- **WHEN** client uploads files via `POST /api/v1/files/upload`
- **THEN** the system chunks supported files using the semantic chunker
- **AND** embeddings are generated and stored in the vector store
- **AND** SQL/DDL and Python graph extraction runs when supported
- **AND** response includes per-file status and ingestion identifiers

#### Scenario: GitHub ingestion indexes code chunks
- **WHEN** client ingests repository files via `POST /api/v1/github/ingest`
- **THEN** the system runs the same chunking, embedding, and indexing pipeline
- **AND** graph extraction runs for SQL/DDL and Python when supported
- **AND** ingestion results are returned with per-file status

### Requirement: Chat endpoints return structured evidence-based responses
The system SHALL return responses from `/api/chat/*` endpoints with structured evidence, next actions, and warnings in a standard JSON format.

#### Scenario: Chat response structure
- **WHEN** any `/api/chat/*` endpoint (except `/deep/stream`) returns a response
- **THEN** it returns JSON matching `ChatResponse` schema with:
  - `response`: string containing the answer
  - `sources`: array of evidence objects
  - `query_type`: string identifying endpoint type
  - `latency_ms`: float for request duration
  - `model`: string identifying the LLM model used (REQUIRED at root level, e.g., `"deepseek/deepseek-r1:free"`)
  - `next_actions`: array of suggested follow-up queries or actions (optional)
  - `warnings`: array of strings for missing evidence or conflicts (optional)
- **AND** the `model` field SHALL always be populated with the actual model that generated the response (primary or fallback)
- **AND** if fallback occurred, the original model failure is NOT exposed to client (logged server-side only)

#### Scenario: Evidence object format
- **WHEN** response includes evidence in `sources` array
- **THEN** each evidence object SHALL contain:
  - `type`: one of `"graph"`, `"chunk"`, or `"doc"`
  - `id`: URN string formatted as `urn:li:{entity_type}:{project_id}:{asset_path}`
  - The `entity_type` portion of the URN SHALL include:
    - `neo4j-node`
    - `neo4j-edge`
    - `qdrant-chunk`
    - `doc`
  - The `asset_path` portion of the URN SHALL follow these conventions:
    - `neo4j-node`: `{label}/{name}` (example: `Table/customers`)
    - `neo4j-edge`: `{type}/{source_label}:{source_name}->{target_label}:{target_name}`
    - `qdrant-chunk`: `{collection}/{point_id}` (example: `code_chunks/12345`)
    - `doc`: `{relative_file_path}`
  - `note`: string describing relevance or context
  - `metadata`: optional object with additional details (e.g., node labels, chunk text excerpt)

#### Scenario: Evidence ID resolution
- **WHEN** client receives evidence with URN ID
- **THEN** client can resolve graph URNs via `/api/v1/lineage/node/{urn}` or `/api/v1/lineage/edge/{urn}` (URL-encoded)
- **AND** client can resolve chunk URNs via `/api/v1/qdrant/chunks/{point_id}`
- **AND** URN format prevents exposing internal implementation details

### Requirement: Chat streaming endpoint uses SSE with chunked JSON
The system SHALL support Server-Sent Events (SSE) streaming for `/api/chat/deep/stream` with incremental answer deltas and final JSON payload.

#### Scenario: SSE streaming format
- **WHEN** client requests `/api/chat/deep/stream`
- **THEN** response uses `Content-Type: text/event-stream`
- **AND** each SSE event is formatted as `data: {json}\n\n`
- **AND** events are sent in this order:
  1. `{"type": "start", "query_type": "deep", "model": "deepseek/deepseek-r1:free"}` (model is the one actually being used, including fallback)
  2. 0..N `{"type": "delta", "content": "partial answer text"}`
  3. `{"type": "done", "response": "full answer", "sources": [...], "next_actions": [...], "warnings": [...], "latency_ms": float, "model": "deepseek/deepseek-r1:free"}`
- **AND** the `model` field in both `start` and `done` events SHALL match the actual model used
- **AND** if fallback occurs before streaming starts, the `start` event reflects the fallback model

#### Scenario: Streaming error handling
- **WHEN** LLM streaming fails mid-response
- **THEN** system sends `{"type": "error", "message": "...", "partial_response": "..."}`
- **AND** client can display partial response and error message
- **AND** connection is closed

#### Scenario: Streaming exemption from strict JSON-only
- **WHEN** `/api/chat/deep/stream` processes request
- **THEN** LLM is allowed to stream free-form text in `delta` events
- **AND** final `done` event MUST contain valid JSON with all required fields
- **AND** if final JSON is malformed, send `error` event instead

### Requirement: Chat error responses with safe fallbacks
The system SHALL handle LLM response parsing failures gracefully without hard-failing on malformed JSON.

#### Scenario: Malformed LLM response fallback
- **WHEN** LLM returns non-JSON or invalid JSON structure
- **THEN** system logs full malformed response with model name and endpoint
- **AND** returns 200 OK with safe fallback JSON:
  ```json
  {
    "response": "I encountered an error generating a structured response. Please try rephrasing your question.",
    "sources": [],
    "query_type": "...",
    "latency_ms": float,
    "model": "google/gemini-2.0-flash-exp:free",
    "next_actions": [],
    "warnings": ["LLM returned malformed response. Falling back to safe response."]
  }
  ```
- **AND** increments `chat_malformed_response_count{endpoint, model}` metric
- **AND** the `model` field reflects the model that failed (for debugging/transparency)
- **AND** warning message does NOT expose technical details to end users

#### Scenario: Partial JSON recovery
- **WHEN** LLM response is valid JSON but missing required fields
- **THEN** system fills missing fields with defaults:
  - Missing `response`: "Unable to generate answer"
  - Missing `sources`: `[]`
  - Missing `next_actions`: `[]`
  - Missing `warnings`: `["LLM response incomplete"]`
- **AND** logs warning with missing field names

### Requirement: Qdrant chunk lookup endpoint
The system SHALL provide a chunk lookup endpoint to resolve Qdrant evidence URNs.

#### Scenario: Chunk lookup by point id
- **WHEN** client requests `GET /api/v1/qdrant/chunks/{point_id}`
- **AND** `point_id` is derived from the `qdrant-chunk` URN `asset_path`
- **THEN** the system returns a JSON payload containing:
  - `id`: the Qdrant point id
  - `collection`: collection name (e.g., `code_chunks`)
  - `payload`: stored metadata (file_path, chunk_type, tables, columns, project_id, repository_id)
  - `content_excerpt`: first 200 characters of the chunk text
- **AND** returns 404 if the point id does not exist

### Requirement: Config endpoint exposes chat model mappings
The system SHALL expose chat endpoint model mappings via `/api/v1/config` for frontend display.

#### Scenario: Config includes chat models
- **WHEN** client requests `GET /api/v1/config`
- **THEN** response includes `chat_endpoint_models` object:
  ```json
  {
    "chat_endpoint_models": {
      "/api/chat/deep": {
        "primary": "deepseek/deepseek-r1-0528:free",
        "secondary": "mistralai/devstral-2512:free",
        "tertiary": "google/gemini-2.0-flash-exp:free"
      },
      "/api/chat/graph": {
        "primary": "mistralai/devstral-2512:free",
        "secondary": "deepseek/deepseek-r1-0528:free",
        "tertiary": "google/gemini-2.0-flash-exp:free"
      },
      "/api/chat/semantic": {
        "primary": "google/gemini-2.0-flash-exp:free",
        "secondary": "qwen/qwen3-4b:free",
        "tertiary": "mistralai/mistral-7b-instruct:free"
      },
      "/api/chat/text": {
        "primary": "google/gemini-2.0-flash-exp:free",
        "secondary": "mistralai/mistral-7b-instruct:free",
        "tertiary": "qwen/qwen3-4b:free"
      },
      "/api/chat/title": {
        "primary": "google/gemini-2.0-flash-exp:free",
        "secondary": "mistralai/mistral-7b-instruct:free",
        "tertiary": "qwen/qwen3-4b:free"
      }
    },
    "free_tier_models": [
      "google/gemini-2.0-flash-exp:free",
      "mistralai/mistral-7b-instruct:free",
      "mistralai/devstral-2512:free",
      "meta-llama/llama-3.1-8b-instruct:free",
      "deepseek/deepseek-r1-0528:free",
      "qwen/qwen3-4b:free"
    ]
  }
  ```
- **AND** config updates are cached for 60 seconds
- **AND** frontend displays current model in chat UI

### Requirement: List Ingestion Logs
The system SHALL provide an endpoint to list ingestion log sessions.

#### Scenario: List ingestion sessions
- **WHEN** a client requests GET /api/v1/ingestion/logs
- **THEN** the system returns a list of ingestion sessions ordered by most recent
- **AND** each item includes ingestion_id, source, project_id, project_status, run_id, status, started_at, completed_at, and filenames

#### Scenario: Filter ingestion sessions
- **WHEN** a client requests GET /api/v1/ingestion/logs with project_id, source, or status filters
- **THEN** the system returns only matching sessions
- **AND** the response includes total and limit metadata

### Requirement: Get Ingestion Log Detail
The system SHALL provide an endpoint to fetch ingestion log details for a session.

#### Scenario: Fetch ingestion log detail
- **WHEN** a client requests GET /api/v1/ingestion/logs/{ingestion_id}
- **THEN** the system returns the ingestion_id and ordered log events
- **AND** the response supports format=json or format=jsonl
- **AND** download=true returns the log as an attachment

#### Scenario: Log detail missing
- **WHEN** a client requests GET /api/v1/ingestion/logs/{ingestion_id} for an unknown ingestion_id
- **THEN** the system returns 404 not found

### Requirement: Upload response correlation
File upload endpoints SHALL return an ingestion_id that can be used to correlate telemetry events with the upload response.

#### Scenario: Uploading files
- **WHEN** a client uploads files to the file upload endpoint
- **THEN** the response includes ingestion_id alongside run metadata
- **AND** ingestion_id matches the telemetry session emitted over WebSocket

### Requirement: Ingestion Log Retrieval Endpoint
The system SHALL expose an endpoint to retrieve ingestion logs by ingestion_id.

#### Scenario: Retrieve ingestion log as JSON
- **WHEN** a client requests GET /api/v1/ingestion/logs/{ingestion_id}?format=json
- **THEN** the system returns a JSON array of log events
- **AND** the response includes the ingestion_id
- **AND** the response is 404 if the ingestion log is not found

#### Scenario: Download ingestion log as JSONL
- **WHEN** a client requests GET /api/v1/ingestion/logs/{ingestion_id}?format=jsonl&download=true
- **THEN** the system returns a JSONL response with content-disposition set for download
- **AND** the filename includes the ingestion_id
- **AND** the response status is 200 when the log exists

### Requirement: Streaming Chat Endpoint
The system SHALL provide a streaming endpoint for real-time chat responses via Server-Sent Events.

#### Scenario: Stream deep analysis response
- **WHEN** client sends POST to /api/chat/deep/stream
- **THEN** server returns Content-Type: text/event-stream
- **AND** response tokens are sent as SSE data events
- **AND** each event contains partial response text
- **AND** final event contains sources and metadata

#### Scenario: Stream error handling
- **WHEN** error occurs during streaming
- **THEN** server sends SSE error event with details
- **AND** connection is closed gracefully
- **AND** client receives actionable error message

#### Scenario: Stream cancellation
- **WHEN** client closes connection during streaming
- **THEN** server stops LLM generation
- **AND** resources are cleaned up
- **AND** no error is logged for client-initiated close

### Requirement: Chat Session Title Generation
The system SHALL provide an endpoint to generate session titles from chat messages.

#### Scenario: Generate title from first message
- **WHEN** client sends POST to /api/chat/title with query
- **THEN** server returns descriptive title (15-30 characters)
- **AND** title summarizes the query topic
- **AND** response time is under 2 seconds

#### Scenario: Title generation fallback
- **WHEN** LLM title generation fails
- **THEN** server returns truncated query as fallback title
- **AND** no error is returned to client
- **AND** fallback is limited to 50 characters

### Requirement: Chat Session Memory Management
The system SHALL provide endpoints to manage chat session memory.

#### Scenario: Delete session memory
- **WHEN** client sends DELETE to /api/chat/session/{session_id}
- **THEN** server schedules memory deletion in background
- **AND** returns 202 Accepted with status message
- **AND** all vectors for session are removed from Qdrant

### Requirement: Chat Graph Artifact Retrieval
The system SHALL provide an endpoint to retrieve persisted graph artifacts from chat responses.

#### Scenario: Retrieve graph artifact by message ID
- **WHEN** client sends GET to /api/chat/session/{session_id}/message/{message_id}/graph
- **THEN** server returns the persisted graph_data for that message
- **AND** response includes nodes array with id, label, type
- **AND** response includes edges array with source, target, relationship
- **AND** response includes metadata object with generation context
- **AND** response is authenticated via JWT

#### Scenario: Graph artifact not found
- **WHEN** client requests graph artifact for non-existent session_id or message_id
- **THEN** server returns 404 Not Found
- **AND** response includes descriptive error message

#### Scenario: Graph artifact persistence
- **WHEN** chat endpoint generates response with graph_data
- **THEN** server persists graph_data to DuckDB chat_artifacts table
- **AND** assigns unique message_id to the response
- **AND** response includes message_id field for artifact retrieval
- **AND** persistence runs asynchronously via background task

#### Scenario: Graph artifact retention
- **WHEN** chat artifacts exceed CHAT_ARTIFACT_RETENTION_DAYS age
- **THEN** system deletes artifacts older than retention period
- **AND** default retention is 90 days
- **AND** retention is configurable via environment variable

### Requirement: JWT Authentication
The system SHALL authenticate all API requests using JWT tokens, except health check endpoints.

#### Scenario: JWT token validation
- **WHEN** request is made to protected endpoint
- **THEN** system extracts Bearer token from Authorization header
- **AND** it validates JWT signature using JWT_SECRET_KEY
- **AND** it checks token expiration timestamp
- **AND** if valid, request proceeds with user_id from token payload
- **AND** if invalid or expired, return 401 Unauthorized

#### Scenario: Token generation on login
- **WHEN** user successfully authenticates via /api/auth/login
- **THEN** system generates JWT token with payload (user_id, role, exp)
- **AND** token expiration is set to 24 hours from issue time
- **AND** token is signed with HS256 algorithm
- **AND** response includes token and user metadata

#### Scenario: Public health endpoints
- **WHEN** request is made to /health or /health/*
- **THEN** no authentication is required
- **AND** endpoint returns status without token check
- **AND** sensitive details (credentials, internal IPs) are excluded

#### Scenario: API key authentication for services
- **WHEN** service-to-service call is made with X-API-Key header
- **THEN** system validates key against stored API keys in database
- **AND** it associates request with service account
- **AND** it logs service API key usage
- **AND** API keys can be rotated without affecting JWT users

### Requirement: Rate Limiting
The system SHALL enforce rate limits on API endpoints to prevent abuse and ensure fair usage.

#### Scenario: Per-user rate limits
- **WHEN** authenticated user makes requests
- **THEN** system tracks request count per user per time window
- **AND** default limit is 100 requests per 10 minutes
- **AND** if limit exceeded, return 429 Too Many Requests
- **AND** response includes Retry-After header

#### Scenario: Per-endpoint rate limits
- **WHEN** request is made to /api/chat/deep
- **THEN** system enforces stricter limit (10 requests per minute)
- **AND** /api/chat/semantic has limit of 30 requests per minute
- **AND** /api/files/upload has limit of 5 requests per minute
- **AND** limits are configurable via environment variables

#### Scenario: Anonymous rate limits
- **WHEN** request is made without authentication (if allowed)
- **THEN** system applies IP-based rate limiting
- **AND** limit is 20 requests per minute per IP
- **AND** rate limit counters are stored in Redis
- **AND** counters expire automatically after time window

#### Scenario: Rate limit headers
- **WHEN** rate-limited request is processed
- **THEN** response includes X-RateLimit-Limit header (total allowed)
- **AND** it includes X-RateLimit-Remaining header (requests left)
- **AND** it includes X-RateLimit-Reset header (timestamp of window reset)
- **AND** headers allow clients to implement backoff

### Requirement: Audit Logging
The system SHALL log all sensitive operations to immutable audit log for compliance and security monitoring.

#### Scenario: Ingestion audit log
- **WHEN** files are ingested via /api/v1/files/upload
- **THEN** system logs event with (timestamp, user_id, file_count, file_names, project_id)
- **AND** log entry is written to audit log storage (append-only)
- **AND** log includes client IP address and user agent
- **AND** log cannot be modified or deleted by application

#### Scenario: Query audit log
- **WHEN** RAG query is executed via /api/chat/*
- **THEN** system logs event with (timestamp, user_id, query_text_hash, query_type, latency_ms)
- **AND** full query text is logged only if AUDIT_LOG_FULL_QUERIES=true
- **AND** log includes response status (success, error, timeout)
- **AND** sensitive PII in queries is redacted per regex rules

#### Scenario: Admin action audit log
- **WHEN** admin performs privileged action (delete project, modify user role)
- **THEN** system logs event with (timestamp, admin_user_id, action_type, target_resource, metadata)
- **AND** log includes before/after state for modifications
- **AND** log entry is written synchronously (cannot be lost)
- **AND** failed admin actions are also logged

#### Scenario: Audit log retention
- **WHEN** audit logs are older than AUDIT_LOG_RETENTION_DAYS (default: 90)
- **THEN** system archives logs to cold storage (S3, Glacier)
- **AND** archived logs are compressed and encrypted
- **AND** active audit log table is partitioned by month
- **AND** retention policy complies with regulatory requirements

### Requirement: Secure Configuration Management
The system SHALL require all sensitive credentials via environment variables and reject hardcoded defaults in production.

#### Scenario: Required credentials validation
- **WHEN** system starts in production mode (ENVIRONMENT=production)
- **THEN** it validates NEO4J_PASSWORD is set via environment variable
- **AND** it validates JWT_SECRET_KEY is set and >= 32 characters
- **AND** it validates ALLOWED_ORIGINS is explicitly configured
- **AND** if any required variable is missing, system fails to start with clear error

#### Scenario: Development mode defaults
- **WHEN** system starts in development mode (ENVIRONMENT=development)
- **THEN** it allows default values for non-sensitive config (OLLAMA_HOST=localhost)
- **AND** it logs warnings for missing credentials
- **AND** it does not fail startup but marks services as degraded

#### Scenario: CORS origin validation
- **WHEN** cross-origin request is received in production
- **THEN** system checks Origin header against ALLOWED_ORIGINS list
- **AND** only exact matches are allowed (no wildcards in production)
- **AND** rejected origins return 403 Forbidden
- **AND** ALLOWED_ORIGINS cannot be "*" in production mode

#### Scenario: Credential exposure prevention
- **WHEN** /health or /api/config endpoints return system info
- **THEN** passwords, API keys, and secrets are redacted
- **AND** only non-sensitive config is returned (timeouts, feature flags)
- **AND** environment variables are never echoed in responses
- **AND** logs mask credentials with "***" before writing

### Requirement: Secure Admin Restart Endpoint
The system SHALL protect the admin restart endpoint to prevent unauthorized process restarts.

#### Scenario: Auth required for restart
- **WHEN** a client calls `/admin/restart`
- **THEN** the request MUST be authenticated/authorized (or restricted to local/dev mode)
- **AND** unauthorized requests receive 401/403
- **AND** successful calls return a confirmation before shutdown/restart begins

#### Scenario: Restart disabled in prod by default
- **WHEN** the service runs in production configuration
- **THEN** `/admin/restart` is disabled or requires explicit feature flag to enable
- **AND** requests without the flag return 404/403

### Requirement: Validate Lineage Node Type Filter
The system SHALL validate lineage node type filters to prevent Cypher injection and malformed queries.

#### Scenario: Whitelisted type labels only
- **WHEN** a client requests `/api/v1/lineage/nodes?type=Table`
- **THEN** the type value is validated against a known whitelist (e.g., Table, Column, View)
- **AND** invalid values return 422 with a clear message
- **AND** Cypher queries are built with parameterization or safe label insertion

### Requirement: Graph-Aware Chat Responses
The system SHALL generate graph-aware chat responses using accurate graph statistics.

#### Scenario: Stats use node type counts
- **WHEN** generating graph-aware prompts
- **THEN** the system uses node type counts from `node_types` (e.g., Table, View, Column)
- **AND** reported counts match `get_stats()` results
- **AND** missing types default to zero without breaking the prompt

