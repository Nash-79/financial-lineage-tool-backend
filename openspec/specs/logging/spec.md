# logging Specification

## Purpose
TBD - created by archiving change cleanup-and-organize-backend. Update Purpose after archive.
## Requirements
### Requirement: Structured Logging Format
All logs SHALL use consistent structured format with standard fields.

#### Scenario: Log message format
- **WHEN** log message is written
- **THEN** it includes timestamp
- **AND** it includes logger name (module)
- **AND** it includes log level
- **AND** it includes message

#### Scenario: Request logging
- **WHEN** API request is logged
- **THEN** it includes request ID
- **AND** it includes HTTP method
- **AND** it includes path
- **AND** it includes status code
- **AND** it includes response time

#### Scenario: Service operation logging
- **WHEN** service operation is logged
- **THEN** it includes operation name
- **AND** it includes operation latency
- **AND** it includes relevant identifiers (user_id, file_id, etc.)

### Requirement: Appropriate Log Levels
Logs SHALL use appropriate severity levels for different event types.

#### Scenario: DEBUG level usage
- **WHEN** detailed diagnostic info is needed
- **THEN** DEBUG level is used
- **AND** logs include variable values
- **AND** logs include execution flow details
- **AND** DEBUG logs are verbose

#### Scenario: INFO level usage
- **WHEN** normal operational event occurs
- **THEN** INFO level is used
- **AND** logs confirm expected behavior
- **AND** logs track major operations (start/complete)

#### Scenario: WARNING level usage
- **WHEN** unusual but recoverable situation occurs
- **THEN** WARNING level is used
- **AND** logs explain what happened
- **AND** logs indicate if action is needed

#### Scenario: ERROR level usage
- **WHEN** error occurs requiring attention
- **THEN** ERROR level is used
- **AND** stack trace is included
- **AND** error context is provided
- **AND** recovery steps are logged if applicable

### Requirement: API Request Logging
All API requests SHALL be logged with comprehensive context.

#### Scenario: Request start logging
- **WHEN** API request starts
- **THEN** request is logged at INFO level
- **AND** log includes request ID
- **AND** log includes method and path
- **AND** log includes client info if available

#### Scenario: Request completion logging
- **WHEN** API request completes
- **THEN** completion is logged at INFO level
- **AND** log includes status code
- **AND** log includes response time
- **AND** log includes request ID for correlation

#### Scenario: Request error logging
- **WHEN** API request fails
- **THEN** error is logged at ERROR level
- **AND** log includes exception details
- **AND** log includes request payload (sanitized)
- **AND** log includes stack trace

### Requirement: Service Operation Logging
Service layer operations SHALL be logged for observability.

#### Scenario: LLM operation logging
- **WHEN** LLM operation is performed
- **THEN** operation is logged
- **AND** log includes model used
- **AND** log includes prompt (truncated if long)
- **AND** log includes response time
- **AND** log includes token count if available

#### Scenario: Vector operation logging
- **WHEN** vector search is performed
- **THEN** operation is logged
- **AND** log includes query text (sanitized)
- **AND** log includes top_k value
- **AND** log includes number of results returned
- **AND** log includes search latency

#### Scenario: Graph operation logging
- **WHEN** graph query is executed
- **THEN** operation is logged
- **AND** log includes query type
- **AND** log includes affected entities
- **AND** log includes operation latency

### Requirement: Ingestion Pipeline Logging
File ingestion pipeline SHALL log all stages for debugging.

#### Scenario: Ingestion start logging
- **WHEN** file ingestion starts
- **THEN** start is logged at INFO level
- **AND** log includes file path
- **AND** log includes file size
- **AND** log includes file type

#### Scenario: Chunking logging
- **WHEN** file is chunked
- **THEN** chunking is logged
- **AND** log includes number of chunks created
- **AND** log includes chunking strategy used
- **AND** log includes average chunk size

#### Scenario: Embedding logging
- **WHEN** chunks are embedded
- **THEN** embedding is logged
- **AND** log includes number of embeddings generated
- **AND** log includes embedding model used
- **AND** log includes total embedding time

#### Scenario: Storage logging
- **WHEN** vectors are stored
- **THEN** storage is logged
- **AND** log includes storage destination
- **AND** log includes number of vectors stored
- **AND** log includes storage operation time

#### Scenario: Ingestion error logging
- **WHEN** ingestion fails
- **THEN** error is logged at ERROR level
- **AND** log includes stage where failure occurred
- **AND** log includes partial progress if any
- **AND** log includes error details

### Requirement: Cache Operation Logging
Cache hits and misses SHALL be logged for performance monitoring.

#### Scenario: Cache hit logging
- **WHEN** cache hit occurs
- **THEN** it's logged at DEBUG level
- **AND** log includes cache key
- **AND** log includes cache type (query/embedding)
- **AND** log includes hit rate

#### Scenario: Cache miss logging
- **WHEN** cache miss occurs
- **THEN** it's logged at DEBUG level
- **AND** log includes cache key
- **AND** log includes reason for miss (not found/expired)

#### Scenario: Cache operation error
- **WHEN** cache operation fails
- **THEN** it's logged at WARNING level
- **AND** log explains degraded operation
- **AND** fallback behavior is logged

### Requirement: Performance Logging
Operation latencies SHALL be logged for performance monitoring.

#### Scenario: Operation timing
- **WHEN** timed operation completes
- **THEN** latency is logged
- **AND** log includes operation name
- **AND** log includes latency in milliseconds
- **AND** slow operations (>1s) are logged at WARNING level

#### Scenario: Resource usage logging
- **WHEN** resource-intensive operation runs
- **THEN** resource usage is logged
- **AND** log includes memory usage if significant
- **AND** log includes CPU time if tracked

### Requirement: Security-Safe Logging
Logs SHALL NOT contain sensitive information.

#### Scenario: Password sanitization
- **WHEN** authentication data is logged
- **THEN** passwords are redacted
- **AND** tokens are redacted
- **AND** API keys are redacted

#### Scenario: PII sanitization
- **WHEN** user data is logged
- **THEN** personally identifiable info is redacted
- **AND** email addresses are masked
- **AND** IP addresses are anonymized if required

#### Scenario: SQL query sanitization
- **WHEN** SQL queries are logged
- **THEN** sensitive data in queries is masked
- **AND** table/column names are preserved
- **AND** query structure is preserved for debugging

### Requirement: Log Configuration
Logging configuration SHALL be adjustable via environment variables.

#### Scenario: Log level configuration
- **WHEN** LOG_LEVEL env var is set
- **THEN** logging uses specified level
- **AND** invalid levels are rejected with error
- **AND** default is INFO if not specified

#### Scenario: Log format configuration
- **WHEN** LOG_FORMAT env var is set
- **THEN** logs use specified format (json/text)
- **AND** format is appropriate for deployment environment
- **AND** JSON format is used in production

#### Scenario: Log output configuration
- **WHEN** LOG_OUTPUT env var is set
- **THEN** logs are sent to specified destination
- **AND** stdout is default
- **AND** file output is supported with rotation

### Requirement: Ingestion Agent Logging
The system SHALL record validation and KG agent outputs in ingestion logs.

#### Scenario: Validation log entry
- **WHEN** validation agent completes post-ingestion
- **THEN** ingestion logs include validation status and gap summary
- **AND** entry includes file_path and ingestion_id

#### Scenario: KG agent log entry
- **WHEN** KG enrichment agent writes edges to Neo4j
- **THEN** ingestion logs include edge counts and model name
- **AND** entry includes confidence statistics (min/avg/max)

### Requirement: Graph Snapshot Logging
The system SHALL log pre-ingestion Neo4j snapshot artifacts.

#### Scenario: Snapshot artifact reference
- **WHEN** snapshot is created before ingestion
- **THEN** ingestion logs include the snapshot artifact path
- **AND** log entry includes node and edge counts
- **AND** log entry includes project name and ingestion_id

### Requirement: Ingestion Log Index Metadata
The system SHALL persist an ingestion log index entry for each ingestion run.

#### Scenario: Create ingestion log index
- **WHEN** an ingestion session starts
- **THEN** the system records an index entry containing ingestion_id, source, project_id, repository_id, run_id, filenames, and started_at
- **AND** the entry is updated with status, project_status, and completed_at when the session finishes
- **AND** entries are ordered by most recent completion time by default

### Requirement: Ingestion Pipeline Stage Telemetry
The ingestion log SHALL include structured stage events for key pipeline steps.

#### Scenario: Stage events recorded
- **WHEN** parsing, chunking, embedding, indexing, or LLM inference is executed
- **THEN** the system records stage events with stage name, status (started/completed/failed), and summary metrics
- **AND** failed stages include error details
- **AND** stages that are not applicable are recorded as skipped

### Requirement: Ingestion Session Log Persistence
The system SHALL persist a structured log file for each ingestion session.

#### Scenario: Ingestion log file creation
- **WHEN** an ingestion session starts
- **THEN** the system creates a JSONL log file for the session
- **AND** the log file name includes the ingestion_id
- **AND** each log entry includes timestamp, event type, and payload
- **AND** log entries are appended in chronological order

### Requirement: On-Demand Verbose Ingestion Logging
The system SHALL support a verbose mode per ingestion session for debugging.

#### Scenario: Verbose mode enabled
- **WHEN** an ingestion request sets verbose to true
- **THEN** the ingestion log includes detailed file-level events
- **AND** verbose events are only recorded for that session
- **AND** standard logging behavior remains unchanged for other sessions

### Requirement: OpenTelemetry Export
The system SHALL export logs, traces, and metrics via OTLP when enabled.

#### Scenario: OTLP export enabled
- **WHEN** OTEL_EXPORTER_OTLP_ENDPOINT is configured
- **THEN** the system exports traces and logs to the OTLP endpoint
- **AND** the service name is included in telemetry attributes
- **AND** export failures are logged without crashing the API

### Requirement: Structured Log Export
The system SHALL forward structured logs to the OpenTelemetry pipeline.

#### Scenario: Log forwarding
- **WHEN** the API emits logs
- **THEN** logs are forwarded to OTLP as log records
- **AND** logs include level, message, and module context

### Requirement: Custom RAG Observability Metrics
The system SHALL emit custom OpenTelemetry metrics for RAG pipeline operations and performance monitoring.

#### Scenario: RAG query latency metrics
- **WHEN** RAG query is executed
- **THEN** system emits histogram metric "rag.query.latency_ms" with labels (endpoint, cache_hit)
- **AND** it tracks p50, p95, p99 latencies
- **AND** metrics are exported to OTLP endpoint
- **AND** metrics can be visualized in SigNoz/Grafana

#### Scenario: Cache performance metrics
- **WHEN** embedding or query cache is accessed
- **THEN** system emits counter metrics "rag.cache.hits" and "rag.cache.misses"
- **AND** it emits gauge metric "rag.cache.hit_rate" updated every 60 seconds
- **AND** metrics include labels (cache_type: embedding|query)
- **AND** alerting can be configured on hit_rate < 0.4

#### Scenario: Ollama OOM error tracking
- **WHEN** Ollama returns OOM error
- **THEN** system emits counter metric "ollama.oom_errors" with labels (model, context_size)
- **AND** it increments counter immediately on error
- **AND** alert is triggered for any OOM error count > 0
- **AND** metric helps diagnose memory issues

#### Scenario: Inference routing metrics
- **WHEN** inference request is routed
- **THEN** system emits counter metric "inference.requests" with labels (provider: ollama|groq|openrouter, success: true|false)
- **AND** it tracks fallback rate (groq_requests / total_requests)
- **AND** it emits cost estimate gauge "inference.estimated_cost_usd"
- **AND** metrics show cost savings from local-first strategy

#### Scenario: SLO compliance metrics
- **WHEN** system processes requests
- **THEN** it tracks SLO compliance for each endpoint
- **AND** it emits gauge "slo.latency_p95_ms" with target threshold
- **AND** it emits gauge "slo.availability_pct" updated every 5 minutes
- **AND** dashboards show red/yellow/green SLO status

