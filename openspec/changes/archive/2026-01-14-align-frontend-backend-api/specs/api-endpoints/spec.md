## ADDED Requirements
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
        "primary": "deepseek/deepseek-r1:free",
        "secondary": "google/gemini-2.0-flash-exp:free",
        "tertiary": "meta-llama/llama-3.1-8b-instruct:free"
      },
      "/api/chat/graph": {
        "primary": "mistralai/devstral-2512:free",
        "secondary": "meta-llama/llama-3.1-8b-instruct:free",
        "tertiary": "google/gemini-2.0-flash-exp:free"
      },
      "/api/chat/semantic": {
        "primary": "google/gemini-2.0-flash-exp:free",
        "secondary": "meta-llama/llama-3.1-8b-instruct:free",
        "tertiary": "mistralai/mistral-7b-instruct:free"
      },
      "/api/chat/text": {
        "primary": "google/gemini-2.0-flash-exp:free",
        "secondary": "meta-llama/llama-3.1-8b-instruct:free",
        "tertiary": "mistralai/mistral-7b-instruct:free"
      },
      "/api/chat/title": {
        "primary": "google/gemini-2.0-flash-exp:free",
        "secondary": "meta-llama/llama-3.1-8b-instruct:free",
        "tertiary": "mistralai/mistral-7b-instruct:free"
      }
    },
    "free_tier_models": [
      "google/gemini-2.0-flash-exp:free",
      "mistralai/mistral-7b-instruct:free",
      "mistralai/devstral-2512:free",
      "meta-llama/llama-3.1-8b-instruct:free",
      "deepseek/deepseek-r1:free"
    ]
  }
  ```
- **AND** config updates are cached for 60 seconds
- **AND** frontend displays current model in chat UI
