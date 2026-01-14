## ADDED Requirements
### Requirement: Ingestion Log Retrieval Endpoint
The system SHALL expose an endpoint to retrieve ingestion logs by ingestion_id.

#### Scenario: Retrieve ingestion log as JSON
- **WHEN** a client requests GET /api/v1/ingestion/logs/{ingestion_id}?format=json
- **THEN** the system returns a JSON array of log events
- **AND** the response includes the ingestion_id
- **AND** the response is 404 if the ingestion log is not found

#### Scenario: Download ingestion log as JSONL
- **WHEN** a client requests GET /api/v1/ingestion/logs/{ingestion_id}?format=jsonl&download=true
- **THEN** the system returns a JSONL response with content-disposition set for download
- **AND** the filename includes the ingestion_id
- **AND** the response status is 200 when the log exists
