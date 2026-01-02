# api-endpoints Specification

## Purpose
TBD - created by archiving change dockerize-backend-with-huggingface. Update Purpose after archive.
## Requirements
### Requirement: Chat Endpoints
The system SHALL provide multiple chat endpoints for different query types.

#### Scenario: Deep chat endpoint
- **WHEN** frontend sends POST to /api/chat/deep
- **THEN** system processes query with deep analysis
- **AND** returns detailed lineage information
- **AND** response includes source citations

#### Scenario: Semantic chat endpoint
- **WHEN** frontend sends POST to /api/chat/semantic
- **THEN** system uses semantic search for context
- **AND** returns natural language response
- **AND** response is optimized for readability

#### Scenario: Graph chat endpoint
- **WHEN** frontend sends POST to /api/chat/graph
- **THEN** system queries knowledge graph
- **AND** returns graph-based lineage paths
- **AND** response includes entity relationships

#### Scenario: Text chat endpoint
- **WHEN** frontend sends POST to /api/chat/text
- **THEN** system processes as simple text query
- **AND** returns basic text-based response
- **AND** minimal graph/vector search overhead

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
The system SHALL provide endpoints for activity tracking and system monitoring.

#### Scenario: Get recent activity
- **WHEN** frontend sends GET to /api/activity/recent
- **THEN** system returns recent system activities
- **AND** includes ingestion events, queries, and errors
- **AND** activities are timestamped and sorted
- **AND** limited to last 100 activities

#### Scenario: Get RAG status
- **WHEN** frontend sends GET to /api/v1/rag/status
- **THEN** system returns RAG pipeline metrics
- **AND** includes cache hit rates
- **AND** includes query latencies
- **AND** indicates LlamaIndex vs legacy mode

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
The system SHALL provide endpoints for data ingestion.

#### Scenario: Ingest SQL file
- **WHEN** frontend sends POST to /api/v1/ingest with file path
- **THEN** system ingests SQL file asynchronously
- **AND** returns {"status": "accepted", "file": "path"}
- **AND** file is chunked, embedded, and indexed
- **AND** progress can be tracked via activity endpoint

#### Scenario: Ingest raw SQL
- **WHEN** frontend sends POST to /api/v1/ingest/sql with SQL content
- **THEN** system parses and ingests SQL directly
- **AND** extracts entities and relationships
- **AND** adds to knowledge graph
- **AND** returns {"status": "success", "source": "name"}

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

