## ADDED Requirements
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
