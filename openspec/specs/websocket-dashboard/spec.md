# websocket-dashboard Specification

## Purpose
TBD - created by archiving change frontend-backend-integration. Update Purpose after archive.
## Requirements
### Requirement: WebSocket Dashboard Connection

System MUST provide WebSocket endpoint for real-time dashboard updates at `/admin/ws/dashboard`.

#### Scenario: Establishing WebSocket connection

- **WHEN** frontend connects to ws://127.0.0.1:8000/admin/ws/dashboard
- **THEN** backend accepts WebSocket connection
- **AND** sends connection_ack message with timestamp
- **AND** connection remains open for bidirectional communication

#### Scenario: Receiving periodic stats updates

- **WHEN** WebSocket connection is established
- **THEN** backend sends stats_update message every 5 seconds
- **AND** message contains current dashboard statistics
- **AND** statistics match /api/v1/stats endpoint data
- **AND** message includes timestamp for ordering

#### Scenario: Connection error handling

- **WHEN** WebSocket connection encounters error
- **THEN** backend logs error with connection details
- **AND** closes connection gracefully
- **AND** cleans up connection tracking resources
- **AND** frontend can reconnect immediately

#### Scenario: Client disconnection

- **WHEN** frontend closes WebSocket connection
- **THEN** backend detects disconnect event
- **AND** removes connection from active connections
- **AND** logs disconnect event
- **AND** frees associated resources

### Requirement: WebSocket Message Format
WebSocket messages SHALL follow standardized JSON structure

#### Scenario: Message type identification
- **WHEN** backend sends WebSocket message
- **THEN** message contains "type" field indicating message category
- **AND** type is one of: connection_ack, stats_update, ingestion_started, ingestion_progress, ingestion_complete, query_complete, error
- **AND** frontend can route message based on type field

#### Scenario: Message data payload
- **WHEN** WebSocket message is sent
- **THEN** message contains "data" field with payload
- **AND** data structure matches message type expectations
- **AND** data is valid JSON serializable
- **AND** data includes all required fields for message type

#### Scenario: Message timestamp
- **WHEN** WebSocket message is created
- **THEN** message contains "timestamp" field in ISO format
- **AND** timestamp represents UTC time of message creation
- **AND** frontend can use timestamp for ordering
- **AND** frontend can detect stale messages

### Requirement: Event Broadcasting
System SHALL broadcast events to all connected WebSocket clients

#### Scenario: Ingestion completion broadcast
- **WHEN** SQL file ingestion completes
- **THEN** backend broadcasts ingestion_complete message
- **AND** message includes file name and status
- **AND** all connected clients receive message
- **AND** message includes processing statistics

#### Scenario: Query completion broadcast
- **WHEN** chat query completes successfully
- **THEN** backend broadcasts query_complete message
- **AND** message includes query type and latency
- **AND** all connected clients receive message
- **AND** message excludes sensitive query content

#### Scenario: Error event broadcast
- **WHEN** system error occurs during processing
- **THEN** backend broadcasts error message
- **AND** message includes error type and severity
- **AND** message excludes sensitive stack traces
- **AND** all connected clients receive message

### Requirement: Connection Limits
System SHALL enforce limits on WebSocket connections

#### Scenario: Maximum connections per IP
- **WHEN** client attempts to open 11th WebSocket connection from same IP
- **THEN** backend rejects connection with 503 status
- **AND** returns error message about connection limit
- **AND** existing connections remain unaffected
- **AND** client can retry after closing existing connections

#### Scenario: Connection cleanup on limit
- **WHEN** connection limit is reached
- **THEN** backend closes oldest idle connection
- **AND** logs connection cleanup event
- **AND** accepts new connection
- **AND** sends disconnect notice to closed connection

### Requirement: WebSocket Security
WebSocket endpoint SHALL implement security measures

#### Scenario: Origin validation
- **WHEN** WebSocket connection request arrives
- **THEN** backend validates Origin header
- **AND** accepts connections from allowed origins
- **AND** rejects connections from unknown origins
- **AND** logs rejected connection attempts

#### Scenario: Message validation
- **WHEN** backend creates WebSocket message
- **THEN** message structure is validated before sending
- **AND** invalid messages are logged and skipped
- **AND** connection remains stable after validation errors
- **AND** error metrics are tracked

#### Scenario: Rate limiting broadcasts
- **WHEN** backend broadcasts messages
- **THEN** rate limit prevents message flooding
- **AND** high-frequency events are throttled
- **AND** critical events bypass throttling
- **AND** throttling is logged for monitoring

### Requirement: Dashboard stats reflect live backend state
The system SHALL compute dashboard stats from live graph and file metadata sources.

#### Scenario: Stats update uses live counts
- **WHEN** frontend calls `GET /api/v1/stats` or receives a `stats_update` message
- **THEN** node and file counts reflect current graph and DuckDB metadata
- **AND** the payload includes `filesProcessed` derived from file metadata
- **AND** the payload format matches the dashboard UI expectations

### Requirement: Ingestion progress broadcast
The system SHALL broadcast ingestion_started and ingestion_progress events for both GitHub and file upload ingestion.

#### Scenario: File upload telemetry
- **WHEN** a file upload ingestion session begins
- **THEN** backend sends ingestion_started with source="upload" and total file count
- **AND** backend emits ingestion_progress events as files are parsed/extracted
- **AND** progress events include current file, status, and errors when present

