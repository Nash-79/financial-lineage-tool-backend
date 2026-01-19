## ADDED Requirements

### Requirement: Loguru as Primary Logging Framework
The system SHALL use Loguru as the primary logging framework for all application logging.

#### Scenario: Loguru initialization
- **WHEN** the application starts
- **THEN** Loguru is configured with appropriate sinks
- **AND** default format includes timestamp, level, module, function, line number
- **AND** request ID context is automatically included when available
- **AND** third-party library noise is suppressed (httpx, httpcore, urllib3)

#### Scenario: Structured JSON logging in production
- **WHEN** `LOG_FORMAT=json` is configured
- **THEN** all logs are serialized as JSON
- **AND** JSON includes all context fields (request_id, trace_id, etc.)
- **AND** JSON is newline-delimited for easy parsing

#### Scenario: Pretty logging in development
- **WHEN** `LOG_FORMAT=pretty` is configured (default)
- **THEN** logs use colorized human-readable format
- **AND** tracebacks are formatted with syntax highlighting
- **AND** long messages are wrapped appropriately

### Requirement: Unified Log Storage Structure
The system SHALL consolidate all logs under a unified directory structure with consistent JSON format.

#### Scenario: Unified log directory
- **WHEN** logs are emitted
- **THEN** all logs are written to `{LOG_PATH}/` with category subdirectories
- **AND** structure is: `logs/app/`, `logs/chat/`, `logs/audit/`, `logs/ingestion/`
- **AND** all log files use JSONL format for consistent parsing

#### Scenario: App log persistence
- **WHEN** application logs are emitted
- **THEN** they are written to `{LOG_PATH}/app/app_{date}.jsonl`
- **AND** files rotate daily
- **AND** old files are compressed after 1 day
- **AND** files older than `LOG_RETENTION_DAYS` are deleted

#### Scenario: Chat log migration
- **WHEN** chat interactions are logged
- **THEN** they are written to `{LOG_PATH}/chat/chat_{date}.jsonl`
- **AND** format includes: timestamp, chat_id, user_id, model, query, response_summary, latency_ms
- **AND** existing chat log format is migrated to JSONL

#### Scenario: Ingestion log consolidation
- **WHEN** ingestion sessions emit logs
- **THEN** session logs are written to `{LOG_PATH}/ingestion/{ingestion_id}.jsonl`
- **AND** index file `{LOG_PATH}/ingestion/_index.jsonl` tracks all sessions
- **AND** each entry includes: timestamp, event_type, file_path, status, metrics

#### Scenario: Log sink configuration
- **WHEN** `LOG_SINK` environment variable is set
- **THEN** logs are sent to configured destinations
- **AND** `stdout` sends to console only
- **AND** `file` sends to file only
- **AND** `both` sends to console and file (default)

### Requirement: Unified Log Viewer API
The system SHALL expose a unified API endpoint for querying ALL log types from one place.

#### Scenario: List all log categories
- **WHEN** GET `/api/v1/logs/categories` is called
- **THEN** returns available log categories: app, chat, audit, ingestion
- **AND** includes total count and error count for each category
- **AND** includes date range (oldest, newest) for each category
- **AND** includes storage size in bytes per category

#### Scenario: List logs with pagination
- **WHEN** GET `/api/v1/logs?limit=100&offset=0` is called
- **THEN** returns paginated log entries from all categories (default 100, max 1000)
- **AND** entries are ordered by timestamp descending
- **AND** response includes: `total_count`, `limit`, `offset`, `has_more`
- **AND** each entry includes its category (app, chat, audit, ingestion)

#### Scenario: Filter logs by category
- **WHEN** GET `/api/v1/logs?category=app` is called
- **THEN** returns only logs from the specified category
- **AND** supports multiple categories: `?category=app,chat`
- **AND** defaults to all categories if not specified

#### Scenario: Filter logs by level
- **WHEN** GET `/api/v1/logs?level=ERROR` is called
- **THEN** returns only logs at ERROR level or above
- **AND** supports levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **AND** level filter applies to app logs; other categories show all

#### Scenario: Filter logs by time range
- **WHEN** GET `/api/v1/logs?start=2024-01-01T00:00:00Z&end=2024-01-02T00:00:00Z` is called
- **THEN** returns logs within the specified time range
- **AND** timestamps are parsed as ISO 8601 UTC

#### Scenario: Filter logs by module
- **WHEN** GET `/api/v1/logs?module=src.services.chat_service` is called
- **THEN** returns logs from the specified module
- **AND** supports partial matching with wildcards (e.g., `src.services.*`)

#### Scenario: Filter logs by request ID
- **WHEN** GET `/api/v1/logs?request_id=abc-123` is called
- **THEN** returns all logs associated with that request across all categories
- **AND** enables full request tracing

#### Scenario: Filter logs by ingestion ID
- **WHEN** GET `/api/v1/logs?ingestion_id=ing-123` is called
- **THEN** returns all logs for that ingestion session
- **AND** includes app logs, ingestion events, and any errors

#### Scenario: Filter logs by chat ID
- **WHEN** GET `/api/v1/logs?chat_id=chat-456` is called
- **THEN** returns all logs for that chat conversation
- **AND** includes chat events and related app logs

#### Scenario: Full-text search
- **WHEN** GET `/api/v1/logs?search=connection+failed` is called
- **THEN** returns logs containing the search terms across all categories
- **AND** search is case-insensitive
- **AND** highlights matched terms in response

#### Scenario: Download logs
- **WHEN** GET `/api/v1/logs/download?category=app&date=2024-01-15` is called
- **THEN** returns the raw JSONL file for that date
- **AND** supports gzip compression via Accept-Encoding header
- **AND** filename includes category and date

### Requirement: Real-time Log Streaming
The system SHALL support WebSocket streaming of logs for live monitoring.

#### Scenario: WebSocket connection
- **WHEN** client connects to `/ws/logs`
- **THEN** connection is established with authentication
- **AND** client receives new logs in real-time from all categories
- **AND** connection includes heartbeat to detect stale clients

#### Scenario: Stream filtering by category
- **WHEN** client sends filter message `{"categories": ["app", "ingestion"]}`
- **THEN** only logs from specified categories are streamed
- **AND** filters can be updated without reconnecting

#### Scenario: Stream filtering by level and module
- **WHEN** client sends filter message `{"level": "ERROR", "module": "src.api.*"}`
- **THEN** only matching logs are streamed
- **AND** filters can be updated without reconnecting
- **AND** default streams all INFO and above

#### Scenario: Stream filtering by ingestion ID
- **WHEN** client sends filter message `{"ingestion_id": "ing-123"}`
- **THEN** only logs for that ingestion session are streamed
- **AND** enables real-time ingestion monitoring in frontend

#### Scenario: Backpressure handling
- **WHEN** client cannot keep up with log volume
- **THEN** oldest undelivered logs are dropped
- **AND** client is notified of dropped count
- **AND** connection is not terminated

### Requirement: OpenTelemetry Trace Correlation
The system SHALL correlate logs with OpenTelemetry traces when tracing is enabled.

#### Scenario: Trace ID in logs
- **WHEN** a log is emitted within an active trace span
- **THEN** the log includes `trace_id` field
- **AND** the log includes `span_id` field
- **AND** trace context is automatically propagated

#### Scenario: Log-to-trace navigation
- **WHEN** viewing a log entry with trace_id
- **THEN** the trace_id can be used to query the trace backend
- **AND** enables correlation between logs and distributed traces

### Requirement: Log Context Management
The system SHALL support contextual logging with automatic field propagation.

#### Scenario: Request context binding
- **WHEN** an API request is received
- **THEN** request_id is bound to logger context
- **AND** all logs within that request include request_id
- **AND** context is cleaned up after request completes

#### Scenario: Custom context fields
- **WHEN** code calls `logger.bind(user_id="123", project_id="abc")`
- **THEN** subsequent logs include those fields
- **AND** binding is scoped to the current context
- **AND** child contexts inherit parent bindings

## MODIFIED Requirements

### Requirement: OpenTelemetry Export
The system SHALL export traces and metrics via OTLP when enabled; logging is handled by Loguru.

#### Scenario: OTLP export enabled
- **WHEN** OTEL_EXPORTER_OTLP_ENDPOINT is configured
- **THEN** the system exports traces to the OTLP endpoint
- **AND** the system exports metrics to the OTLP endpoint
- **AND** the service name is included in telemetry attributes
- **AND** export failures are logged without crashing the API
- **AND** logs are NOT exported via OTLP (handled by Loguru file sink)

#### Scenario: Trace-log correlation
- **WHEN** OpenTelemetry tracing is enabled
- **THEN** Loguru logs include trace_id and span_id fields
- **AND** enables correlation in observability backends like SigNoz

## REMOVED Requirements

### Requirement: Structured Log Export
**Reason**: Loguru handles log persistence directly to files; OpenTelemetry log export adds complexity without benefit for this use case.
**Migration**: Logs are accessible via new `/api/v1/logs` endpoint instead of OTLP log records.
