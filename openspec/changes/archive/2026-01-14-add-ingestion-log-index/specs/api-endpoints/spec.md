## ADDED Requirements
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
