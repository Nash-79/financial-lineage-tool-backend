# API Reference

Complete reference for all Financial Lineage Tool API endpoints.

## Authentication & Rate Limits
- JWT Bearer tokens are required for protected routes (admin, ingestion, files, GitHub, database, ingestion logs). In production or when `JWT_REQUIRED=true`, missing/invalid tokens return 401.
- Optional API keys can be supplied via `X-API-Key`.
- Rate limits (SlowAPI): default `RATE_LIMIT_DEFAULT` (100/minute), chat `RATE_LIMIT_CHAT` (30/minute), ingestion `RATE_LIMIT_INGEST` (10/minute), auth `RATE_LIMIT_AUTH` (5/minute). Responses include `X-RateLimit-*` headers.

## Base URL

```
http://localhost:8000
```

## Interactive Documentation

FastAPI provides auto-generated interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Authentication

Currently, the API does not require authentication (development mode).

## Common Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 503 | Service Unavailable - Service not initialized |
| 500 | Internal Server Error |

## Metadata Legend

> **Note**: This document serves as the source of truth for automated contract testing.  
> Each endpoint includes metadata used by Schemathesis and Playwright to generate test cases.

- **Method**: HTTP verb (GET/POST/PUT/DELETE)
- **Critical**: `@critical` tag indicates endpoint is tested in E2E smoke tests
- **Flow**: User journey this endpoint belongs to (e.g., "Project Lifecycle", "File Ingestion", "Dashboard")
- **Auth**: Authentication requirement (currently all endpoints are open in dev mode)


---

## Projects

### List All Projects

**@critical** - Used in Project Lifecycle smoke test

Get all projects with repository and link counts.

```http
GET /api/v1/projects?limit=100&offset=0
```

**Query Parameters**:
- `limit` (int, optional): Maximum results (1-1000, default: 100)
- `offset` (int, optional): Results to skip (default: 0)

**Response**: `ProjectListResponse`
```json
{
  "projects": [
    {
      "id": "proj-123",
      "name": "Customer Analytics",
      "description": "Customer data pipeline",
      "repository_count": 3,
      "link_count": 5,
      "created_at": "2025-12-31T20:00:00",
      "updated_at": "2025-12-31T20:00:00"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### Create Project

**@critical** - Used in Project Lifecycle smoke test

Create a new project container for repositories.

```http
POST /api/v1/projects
```

**Request**: `ProjectCreate`
```json
{
  "id": "proj-456",
  "name": "Sales Pipeline",
  "description": "Sales data processing"
}
```

**Response**: `Project`
```json
  {
    "id": "proj-456",
    "name": "Sales Pipeline",
    "description": "Sales data processing",
    "repositories": [],
    "links": [],
    "project_links": [],
    "created_at": "2025-12-31T20:00:00",
    "updated_at": "2025-12-31T20:00:00"
  }
```

### Get Project Details

Get complete project information including repositories and links.

```http
GET /api/v1/projects/{project_id}
```

**Response**: `Project`
```json
{
  "id": "proj-123",
  "name": "Customer Analytics",
  "description": "Customer data pipeline",
  "repositories": [
    {
      "id": "repo-1",
      "name": "customer-etl",
      "source_type": "github",
      "url": "https://github.com/org/customer-etl"
    }
  ],
  "links": [],
  "project_links": [],
  "created_at": "2025-12-31T20:00:00",
  "updated_at": "2025-12-31T20:00:00"
}
```

### Create Project Link

Create a manual link between two projects.

```http
POST /api/v1/projects/{project_id}/project-links
```

**Request**: `ProjectLinkCreate`
```json
{
  "target_project_id": "proj-456",
  "description": "Upstream dependency on Sales project"
}
```

**Response**: `ProjectLinkResponse`
```json
{
  "id": "plink-123",
  "source_project_id": "proj-123",
  "target_project_id": "proj-456",
  "link_type": "manual",
  "description": "Upstream dependency on Sales project",
  "created_at": "2025-12-31T20:00:00"
}
```

### List Project Links

List all links involving a project.

```http
GET /api/v1/projects/{project_id}/project-links
```

**Response**:
```json
[
  {
    "id": "plink-123",
    "source_project_id": "proj-123",
    "target_project_id": "proj-456",
    "link_type": "manual",
    "description": "Upstream dependency on Sales project",
    "created_at": "2025-12-31T20:00:00"
  }
]
```

### Delete Project Link

Delete a project-to-project link.

```http
DELETE /api/v1/projects/{project_id}/project-links/{link_id}
```

### Update Project

Update project details (name, description).

```http
PUT /api/v1/projects/{project_id}
```

**Request**: `ProjectUpdate`
```json
{
  "name": "Updated Project Name",
  "description": "Updated description"
}
```

### Delete Project

Delete project and optionally its lineage data.

```http
DELETE /api/v1/projects/{project_id}?delete_data=false
```

**Query Parameters**:
- `delete_data` (bool, optional): If true, also delete Neo4j lineage nodes (default: false)

---

## Files

### Upload Files

**@critical** - Used in File Upload Flow smoke test

Upload files for lineage ingestion with project scoping.

```http
POST /api/v1/files/upload
```

**Request**: `multipart/form-data`
- `files` (file[], required): Files to upload (.sql, .ddl, .csv, .json)
- `project_id` (string, required): Project ID to associate files with
- `repository_id` (string, optional): Repository ID (creates new if omitted)
- `repository_name` (string, optional): Repository name (required if repository_id omitted)
- `instructions` (string, optional): Additional guidance for lineage extraction
- `dialect` (string, optional): SQL dialect for parsing (default: auto)
- `verbose` (bool, optional): Enable verbose ingestion logging

**Response**: `UploadResponse`
```json
{
  "success": true,
  "files_processed": 3,
  "files_failed": 0,
  "ingestion_id": "ingest-123",
    "snapshot": {
      "path": "data/customer_analytics/20260113_120000_001_upload_customer_analytics/KG/neo4j_snapshot_20260113_120000_ingest-123.json",
      "node_count": 120,
      "edge_count": 220,
      "timestamp": "20260113_120000",
      "project_name": "Customer Analytics",
      "project_id": "proj-123",
      "run_id": "run-789",
      "ingestion_id": "ingest-123"
    },
  "results": [
    {
      "filename": "customer_schema.sql",
      "status": "success",
      "file_id": "file-123",
      "nodes_created": 15,
      "message": "Processed successfully",
      "validation": {
        "status": "passed",
        "missing_nodes_count": 0,
        "missing_edges_count": 0
      },
      "kg_enrichment": {
        "model": "mistralai/devstral-2512:free",
        "proposed_edges": 2,
        "accepted_edges": 1,
        "confidence_avg": 0.87
      }
    }
  ],
  "repository_id": "repo-456",
  "run_id": "run-789"
}
```

### Get Upload Configuration

Get current upload settings (allowed extensions, size limits).

```http
GET /api/v1/files/config
```

**Response**: `UploadConfig`
```json
{
  "allowed_extensions": ["sql", "ddl", "csv", "json"],
  "max_file_size_mb": 50
}
```

### Update Upload Configuration

Update upload settings.

```http
PUT /api/v1/files/config
```

**Request**: `UploadConfigUpdate`
```json
{
  "allowed_extensions": ["sql", "ddl"],
  "max_file_size_mb": 100
}
```

---

## WebSocket

### Dashboard Real-Time Updates

**@critical** - Used in Dashboard WebSocket Connection smoke test

WebSocket endpoint for real-time dashboard updates.

```http
WS /api/v1/ws/dashboard
```

**Connection**: Upgrade to WebSocket protocol

**Messages Received** (from server):
```json
{
  "type": "connection_ack",
  "message": "Connected to dashboard updates",
  "timestamp": "2025-12-31T20:00:00"
}
```

```json
{
  "type": "stats_update",
  "data": {
    "totalNodes": 1523,
    "filesProcessed": 234,
    "databaseTables": 89,
    "activeQueries": 12
  },
  "timestamp": "2025-12-31T20:00:00"
}
```

**Connection States**:
- `Connecting`: Initial connection attempt
- `Live`: Successfully connected and receiving updates
- `Offline`: Disconnected or connection failed

**Error Codes**:
- `1006`: Abnormal closure (connection lost)
- `403`: Forbidden (CORS or authentication issue)

### Get WebSocket Configuration

Get WebSocket URL for frontend clients.

```http
GET /api/v1/config/websocket
```

**Response**:
```json
{
  "websocket_url": "ws://127.0.0.1:8000/api/v1/ws/dashboard"
}
```

---

## Configuration Endpoints

### Get SQL Dialects

Retrieve enabled SQL dialects for ingestion and parsing.

```http
GET /api/v1/config/sql-dialects
```

**Response**:
```json
[
  {
    "id": "tsql",
    "display_name": "T-SQL (SQL Server)",
    "sqlglot_key": "tsql",
    "is_default": true,
    "enabled": true
  },
  {
    "id": "duckdb",
    "display_name": "DuckDB",
    "sqlglot_key": "duckdb",
    "is_default": false,
    "enabled": true
  }
]
```

---

## Health & Monitoring

### Check System Health

Get health status of all services.

```http
GET /health
```

**Response**: `HealthResponse`
```json
{
  "status": "healthy",
  "services": {
    "api": "up",
    "ollama": "up",
    "qdrant": "up",
    "neo4j": "up",
    "llamaindex": "up",
    "rag_mode": "llamaindex"
  },
  "timestamp": "2025-12-31T20:00:00"
}
```

### Get RAG Status

Get RAG pipeline status and metrics.

```http
GET /api/v1/rag/status
```

**Response**: `RAGStatusResponse`
```json
{
  "mode": "llamaindex",
  "total_queries": 1523,
  "cache_hit_rate": 0.67,
  "avg_latency_ms": 234.5,
  "status": "healthy"
}
```

### Get Activity Metrics

Get aggregated activity tracking metrics.

```http
GET /api/v1/metrics/activity
```

**Response**:
```json
{
  "total_requests": 5432,
  "success_rate": 0.98,
  "total_queries": 1523,
  "total_ingestions": 234,
  "avg_latency_ms": 187.3,
  "cache_hit_rate": 0.67,
  "top_endpoints": [
    {"endpoint": "/api/chat/semantic", "count": 856},
    {"endpoint": "/api/v1/lineage/query", "count": 667}
  ],
  "error_types": {
    "ValidationError": 12,
    "TimeoutError": 3
  }
}
```

### Get Recent Events

Get recent activity events with details.

```http
GET /api/v1/metrics/events?limit=100
```

**Query Parameters**:
- `limit` (int, optional): Maximum events to return (max: 1000, default: 100)

**Response**:
```json
{
  "events": [
    {
      "event_id": "evt_123",
      "event_type": "query",
      "endpoint": "/api/chat/semantic",
      "timestamp": "2025-12-31T20:00:00",
      "latency_ms": 234.5,
      "status": "success",
      "metadata": {
        "method": "POST",
        "status_code": 200
      }
    }
  ],
  "total_events": 5432
}
```

---

## Chat Endpoints

### ChatRequest Model

All chat endpoints accept the following request format:

```json
{
  "query": "string (required)",
  "history": [{"role": "user/assistant", "content": "..."}],
  "context": {"key": "value"},
  "session_id": "optional-session-id",
  "skip_memory": false
}
```

**Parameters**:
- `query` (string, required): The user's question or prompt
- `history` (array, optional): Conversation history (not currently used)
- `context` (object, optional): Additional context for filtering
- `session_id` (string, optional): Session ID for memory context retrieval
- `skip_memory` (boolean, optional): Skip memory context retrieval for faster response (saves ~300ms). Default: false

### Deep Analysis Chat

Comprehensive analysis with maximum context (top 10 results).

```http
POST /api/chat/deep
```

**Request**: `ChatRequest`
```json
{
  "query": "What tables are used in the customer analysis pipeline?",
  "context": {
    "database": "production",
    "schema": "analytics"
  },
  "session_id": "sess-123",
  "skip_memory": false
}
```

**Response**: `ChatResponse`
```json
{
  "response": "The customer analysis pipeline uses 3 main tables...",
  "sources": [
    {
      "file_path": "schemas/customer_analytics.sql",
      "chunk_type": "view",
      "score": 0.89
    }
  ],
  "query_type": "deep",
  "latency_ms": 456.7,
  "graph_data": {
    "nodes": [{"id": "t1", "data": {"label": "customers", "type": "Table"}}],
    "edges": [{"id": "e1", "source": "t1", "target": "t2", "label": "DEPENDS_ON"}]
  }
}
```

### Deep Analysis Chat (Streaming)

Streaming version using Server-Sent Events for real-time response.

```http
POST /api/chat/deep/stream
```

**Request**: `ChatRequest` (same as `/deep`)

**Response**: `text/event-stream`

Event types:
- `chunk`: Partial response text
- `done`: Final event with sources and metadata
- `error`: Error event

```
data: {"type": "chunk", "content": "The customer"}

data: {"type": "chunk", "content": " analysis pipeline"}

data: {"type": "done", "sources": [...], "graph_data": {...}, "latency_ms": 456.7}
```

**Frontend Usage (JavaScript)**:
```javascript
const eventSource = new EventSource('/api/chat/deep/stream', {
  method: 'POST',
  body: JSON.stringify({ query: "...", session_id: "..." })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'chunk') {
    // Append to response
    responseText += data.content;
  } else if (data.type === 'done') {
    // Handle completion
    eventSource.close();
  }
};
```

### Semantic Search Chat

Similarity-based retrieval optimized for natural language.

```http
POST /api/chat/semantic
```

**Request**: `ChatRequest`
```json
{
  "query": "Find all stored procedures that calculate revenue",
  "context": null
}
```

**Response**: `ChatResponse`
```json
{
  "response": "Found 5 stored procedures that calculate revenue...",
  "sources": [
    {
      "text": "CREATE PROCEDURE sp_calc_monthly_revenue...",
      "file_path": "procs/revenue_calculations.sql"
    }
  ],
  "query_type": "semantic",
  "latency_ms": 234.5
}
```

**Hybrid Search Example**:
- Enable `ENABLE_HYBRID_SEARCH=true` to blend keyword (BM25) and semantic results.
- Example query: `"gross margin by product"` will match exact SQL text and related embeddings.

### Graph-Based Chat

Focus on relationships and lineage using graph database.

```http
POST /api/chat/graph
```

**Request**: `ChatRequest`
```json
{
  "query": "Show me the lineage of the fact_sales table"
}
```

**Response**: `ChatResponse`
```json
{
  "response": "The fact_sales table has 3 upstream sources...",
  "sources": [
    {
      "type": "graph_stats",
      "data": {
        "nodes": 156,
        "Table": 45,
        "View": 23,
        "Column": 88
      }
    }
  ],
  "query_type": "graph",
  "latency_ms": 123.4
}
```

### Simple Text Chat

Direct LLM queries without heavy RAG processing.

```http
POST /api/chat/text
```

**Request**: `ChatRequest`
```json
{
  "query": "Explain what a data warehouse dimension table is"
}
```

**Response**: `ChatResponse`
```json
{
  "response": "A dimension table is a structure in a data warehouse...",
  "sources": [],
  "query_type": "text",
  "latency_ms": 89.2
}
```

### Generate Session Title

Generate a short descriptive title for a chat session.

```http
POST /api/chat/title
```

**Request**: `ChatRequest`
```json
{
  "query": "What is the lineage of the customers table?"
}
```

**Response**:
```json
{
  "title": "Customer Table Lineage"
}
```

**Notes**:
- Generates a 15-30 character title
- Falls back to truncated query if generation fails

### Delete Session Memory

Delete chat memory for a specific session.

```http
DELETE /api/chat/session/{session_id}
```

**Path Parameters**:
- `session_id` (string, required): Session identifier

**Response** (202 Accepted):
```json
{
  "status": "accepted",
  "message": "Memory deletion scheduled for sess-123"
}
```

**Response** (Memory not initialized):
```json
{
  "status": "ignored",
  "message": "Memory service not initialized"
}
```

---

## Lineage Endpoints

### Natural Language Lineage Query

Query data lineage using natural language.

```http
POST /api/v1/lineage/query
```

**Request**: `LineageQueryRequest`
```json
{
  "question": "Where does the customer_revenue column come from?"
}
```

**Response**: `LineageResponse`
```json
{
  "question": "Where does the customer_revenue column come from?",
  "answer": "The customer_revenue column is derived from...",
  "sources": [
    "schemas/analytics/fact_revenue.sql",
    "views/customer_metrics.sql"
  ],
  "graph_entities": [
    "fact_revenue",
    "dim_customer",
    "customer_revenue"
  ],
  "confidence": 0.85
}
```

### Get All Lineage Nodes

Retrieve all nodes from the knowledge graph.

```http
GET /api/v1/lineage/nodes
```

**Response**:
```json
[
  {
    "id": "table_fact_sales",
    "label": "fact_sales",
    "type": "table",
    "metadata": {
      "schema": "dbo",
      "columns": 15
    }
  }
]
```

### Get All Lineage Edges

Retrieve all relationships from the knowledge graph.

```http
GET /api/v1/lineage/edges
```

**Response**:
```json
[
  {
    "source": "view_customer_metrics",
    "target": "fact_sales",
    "type": "DEPENDS_ON",
    "properties": {}
  }
]
```

### Search Lineage

Search for entities by name.

```http
GET /api/v1/lineage/search?q=customer
```

**Query Parameters**:
- `q` (string, required): Search query

**Response**:
```json
{
  "nodes": [
    {
      "id": "table_customers",
      "label": "customers",
      "type": "table",
      "metadata": {
        "schema": "dbo"
      }
    }
  ],
  "edges": []
}
```

### Get Node Lineage

Get upstream/downstream lineage for a specific node.

```http
GET /api/v1/lineage/node/{node_id}?direction=both
```

**Path Parameters**:
- `node_id` (string, required): Node identifier

**Query Parameters**:
- `direction` (string, optional): `upstream`, `downstream`, or `both` (default: `both`)

**Response**:
```json
{
  "nodes": [
    {
      "id": "table_customers",
      "label": "customers",
      "type": "table",
      "metadata": {}
    }
  ],
  "edges": []
}
```

---

## Project Endpoints

### Get Project Context

Retrieve context information for a specific project.

```http
GET /api/v1/projects/{project_id}/context
```

**Path Parameters**:
- `project_id` (string, required): Project identifier

**Response**:
```json
{
  "description": "Financial risk calculation engine...",
  "format": "text",
  "source_entities": ["trade_repository", "market_data"],
  "target_entities": ["risk_report"],
  "domain_hints": ["basel", "market risk"],
  "updated_at": "2025-12-31T20:00:00"
}
```

### Update Project Context

Update context information for a project.

```http
PUT /api/v1/projects/{project_id}/context
```

**Request**: `ProjectContext`
```json
{
  "description": "Financial risk calculation engine...",
  "format": "text",
  "source_entities": ["trade_repository", "market_data"],
  "target_entities": ["risk_report"],
  "domain_hints": ["basel", "market risk"]
}
```

**Response**:
```json
{
  "description": "Financial risk calculation engine...",
  "updated_at": "2025-12-31T20:00:00"
  // ... (returns updated context)
}
```

### Upload Project Context File

Upload a markdown file as project context (Stub - 501 Not Implemented).

```http
POST /api/v1/projects/{project_id}/context/upload
```

---


## Ingestion Endpoints

### Ingest File

Ingest SQL file or directory for analysis (background processing).

```http
POST /api/v1/ingest
```

**Request**: `IngestRequest`
```json
{
  "file_path": "/path/to/schema.sql",
  "file_type": "sql",
  "dialect": "auto"
}
```

  **Response**:
  ```json
  {
    "status": "accepted",
    "file": "/path/to/schema.sql",
    "project_id": "proj-123",
    "run_id": "run-456",
    "ingestion_id": "ingest-789",
    "run_dir": "data/customer_analytics/20260113_120000_001_ingest_schema"
  }
  ```

**Notes**:
- Processing happens in the background
- File is chunked, embedded, and stored in Qdrant
- Entities are extracted and stored in Neo4j
- Re-ingesting the same `file_path` purges prior chunks and graph nodes before insert (idempotent)

### Ingest Raw SQL

Parse and ingest raw SQL content directly.

```http
POST /api/v1/ingest/sql
```

**Request**: `SqlIngestRequest`
```json
{
  "sql_content": "CREATE TABLE customers (\n  id INT PRIMARY KEY,\n  name VARCHAR(100)\n);",
  "dialect": "auto",
  "source_file": "manual_input.sql"
}
```

**Response**:
```json
{
  "status": "success",
  "source": "manual_input.sql"
}
```

**Notes**:
- Re-ingesting the same `source_file` purges prior chunks and graph nodes before insert

### List Ingestion Sessions

List all ingestion log sessions with optional filters, ordered by most recent.

```http
GET /api/v1/ingestion/logs?project_id=&source=&status=&limit=50
```

**Query Parameters**:
- `project_id` (string, optional): Filter by project ID
- `source` (string, optional): Filter by source (`upload` or `github`)
- `status` (string, optional): Filter by status (`pending`, `in_progress`, `completed`, `completed_with_errors`, `failed`)
- `limit` (int, optional): Maximum results (1-200, default: 50)

**Response**: `IngestionLogsResponse`
```json
{
  "sessions": [
    {
      "ingestion_id": "ingest-456",
      "source": "github",
      "project_id": "proj-789",
      "project_status": "active",
      "repository_id": "repo-012",
      "run_id": "run-345",
      "status": "completed",
      "started_at": "2026-01-09T13:00:00",
      "completed_at": "2026-01-09T13:05:30",
      "filenames": ["schema.sql", "views.sql"],
      "source_repo": "owner/repository"
    },
    {
      "ingestion_id": "ingest-123",
      "source": "upload",
      "project_id": "proj-456",
      "project_status": "active",
      "repository_id": "repo-789",
      "run_id": "run-012",
      "status": "completed_with_errors",
      "started_at": "2026-01-09T12:00:00",
      "completed_at": "2026-01-09T12:03:15",
      "filenames": ["data.sql"],
      "source_repo": null
    }
  ],
  "total": 2,
  "limit": 50
}
```

**Notes**:
- Results are ordered by `started_at` descending (most recent first)
- Index files are created per ingestion run in `data/*/ingestion_index.json`
- Filters can be combined (e.g., `?source=github&status=completed`)

### Get Ingestion Session Logs

Retrieve detailed persisted logs for a specific ingestion session.

```http
GET /api/v1/ingestion/logs/{ingestion_id}?format=json|jsonl&download=false
```

**Query Parameters**:
- `format` (string, optional): `json` (pretty-printed) or `jsonl` (default: `json`)
- `download` (bool, optional): Return as attachment if true (default: false)

**Response** (`format=json`):
```json
{
  "ingestion_id": "ingest-123",
  "events": [
    {
      "timestamp": "2026-01-08T22:08:12.000Z",
      "type": "ingestion_started",
      "level": "info",
      "payload": {
        "total_files": 3
      }
    }
  ]
}
```

**Notes**:
- `stage_event` entries include post-ingestion stages:
  - `graph_snapshot` (snapshot_path, node_count, edge_count)
  - `validation` (status, missing_nodes, missing_edges)
  - `kg_enrichment` (model, proposed_edges, accepted_edges, confidence_* stats)

---

## Graph Endpoints

### Get Graph Statistics

Get knowledge graph statistics.

```http
GET /api/v1/graph/stats
```

**Response**:
```json
{
  "nodes": 156,
  "relationships": 234,
  "Table": 45,
  "View": 23,
  "Column": 88,
  "Procedure": 12
}
```

### Add Entity

Create a new entity in the knowledge graph.

```http
POST /api/v1/graph/entity
```

**Request**: `EntityRequest`
```json
{
  "entity_id": "table_new_customers",
  "entity_type": "Table",
  "name": "new_customers",
  "properties": {
    "schema": "dbo",
    "created_date": "2025-12-31"
  }
}
```

**Response**:
```json
{
  "status": "created",
  "entity_id": "table_new_customers"
}
```

### Add Relationship

Create a relationship between entities.

```http
POST /api/v1/graph/relationship
```

**Request**: `RelationshipRequest`
```json
{
  "source_id": "view_customer_summary",
  "target_id": "table_customers",
  "relationship_type": "DEPENDS_ON",
  "properties": {
    "join_column": "customer_id"
  }
}
```

**Response**:
```json
{
  "status": "created"
}
```

### Get Entity

Retrieve entity by ID.

```http
GET /api/v1/graph/entity/{entity_id}
```

**Path Parameters**:
- `entity_id` (string, required): Entity identifier

**Response**:
```json
{
  "id": "table_customers",
  "entity_type": "Table",
  "name": "customers",
  "properties": {
    "schema": "dbo"
  }
}
```

### Search Entities

Search entities by name.

```http
GET /api/v1/graph/search?name=customer
```

**Query Parameters**:
- `name` (string, required): Entity name to search

**Response**:
```json
[
  {
    "id": "table_customers",
    "name": "customers",
    "entity_type": "Table"
  }
]
```

### Get Entity Lineage

Get upstream/downstream lineage for an entity.

```http
GET /api/v1/graph/lineage/{entity_id}?direction=both&max_depth=5
```

**Path Parameters**:
- `entity_id` (string, required): Entity identifier

**Query Parameters**:
- `direction` (string, optional): `upstream`, `downstream`, or `both` (default: `both`)
- `max_depth` (int, optional): Maximum traversal depth (default: 5)

**Response**:
```json
{
  "entity_id": "view_customer_metrics",
  "upstream": [
    {"id": "table_customers", "name": "customers"},
    {"id": "table_transactions", "name": "transactions"}
  ],
  "downstream": [
    {"id": "view_customer_summary", "name": "customer_summary"}
  ]
}
```

---

## Admin Endpoints

### List Ollama Models

Get available Ollama models.

```http
GET /api/v1/models
```

**Response**:
```json
{
  "models": [
    {
      "name": "llama3.1:8b",
      "modified_at": "2025-12-01T10:00:00Z",
      "size": 4661211648
    },
    {
      "name": "nomic-embed-text",
      "modified_at": "2025-12-01T09:00:00Z",
      "size": 274301184
    }
  ]
}
```

### Get Dashboard Statistics

Get high-level dashboard metrics.

```http
GET /api/v1/stats
```

**Response**:
```json
{
  "totalNodes": 156,
  "filesProcessed": 23,
  "databaseTables": 45,
  "activeQueries": 5,
  "trends": {
    "nodes": {"value": 12, "isPositive": true},
    "files": {"value": 8, "isPositive": true}
  }
}
```

### Get Recent Activity

Get recent activity items.

```http
GET /api/v1/activity/recent
```

**Response**:
```json
[
  {
    "id": "1",
    "type": "ingestion",
    "message": "Processed SQL file successfully",
    "timestamp": "2025-12-31T20:00:00"
  }
]
```

### Get Recent Files

Get recently processed files.

```http
GET /api/v1/files/recent
```

**Response**:
```json
[
  {
    "id": "1",
    "name": "customer_schema.sql",
    "type": "file",
    "status": "processed",
    "updatedAt": "2025-12-31T20:00:00"
  }
]
```

### List All Files

Get all files in storage.

```http
GET /api/v1/files
```

**Response**:
```json
[]
```

**Note**: File listing to be implemented.

### Get File Statistics

Get file processing statistics.

```http
GET /api/v1/files/stats
```

**Response**:
```json
{
  "total": 0,
  "processed": 0,
  "pending": 0,
  "errors": 0
}
```

**Note**: File statistics tracking to be implemented.

### Search Files

Search for files by query.

```http
GET /api/v1/files/search?q=customer
```

**Query Parameters**:
- `q` (string, required): Search query

**Response**:
```json
[]
```

**Note**: File search to be implemented.

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Errors

**Service Not Initialized (503)**:
```json
{
  "detail": "Agent not initialized"
}
```

**Not Found (404)**:
```json
{
  "detail": "Entity not found"
}
```

**File Not Found (404)**:
```json
{
  "detail": "File not found: /path/to/file.sql"
}
```

---

## WebSocket Endpoints

### Dashboard Real-time Updates

Connect to receive real-time dashboard statistics and system events.

```http
WS /api/v1/ws/dashboard
```

**Message Types**:
- `stats_update`: Periodic statistics payload
- `connection_ack`: Connection confirmation
- `ingestion_complete`: Event notification
- `error`: Error notification

**Example Message**:
```json
{
  "type": "stats_update",
  "data": {
    "totalNodes": 156,
    "filesProcessed": 23
  },
  "timestamp": "2025-12-31T20:00:00"
}
```

**Validation Error (422)**:
```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Rate Limiting

Currently, there are no rate limits (development mode). In production, rate limiting will be implemented.

## WebSocket Support

WebSocket support for real-time updates is planned for future releases.

## Pagination

Pagination is not currently implemented but is planned for endpoints that return large datasets (nodes, edges, files).

## Filtering

Most list endpoints support basic filtering via query parameters. Advanced filtering capabilities are planned for future releases.

## Versioning

The API uses URL path versioning (e.g., `/api/v1/`). Breaking changes will result in a new version number.
