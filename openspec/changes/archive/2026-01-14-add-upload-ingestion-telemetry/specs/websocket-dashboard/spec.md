## MODIFIED Requirements
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

## ADDED Requirements
### Requirement: Ingestion progress broadcast
The system SHALL broadcast ingestion_started and ingestion_progress events for both GitHub and file upload ingestion.

#### Scenario: File upload telemetry
- **WHEN** a file upload ingestion session begins
- **THEN** backend sends ingestion_started with source="upload" and total file count
- **AND** backend emits ingestion_progress events as files are parsed/extracted
- **AND** progress events include current file, status, and errors when present
