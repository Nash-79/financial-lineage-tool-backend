# API Reference

Complete reference for all Financial Lineage Tool API endpoints.

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
  }
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
  "latency_ms": 456.7
}
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
  "file_type": "sql"
}
```

**Response**:
```json
{
  "status": "accepted",
  "file": "/path/to/schema.sql"
}
```

**Notes**:
- Processing happens in the background
- File is chunked, embedded, and stored in Qdrant
- Entities are extracted and stored in Neo4j

### Ingest Raw SQL

Parse and ingest raw SQL content directly.

```http
POST /api/v1/ingest/sql
```

**Request**: `SqlIngestRequest`
```json
{
  "sql_content": "CREATE TABLE customers (\n  id INT PRIMARY KEY,\n  name VARCHAR(100)\n);",
  "dialect": "tsql",
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
