## ADDED Requirements
### Requirement: Upload response correlation
File upload endpoints SHALL return an ingestion_id that can be used to correlate telemetry events with the upload response.

#### Scenario: Uploading files
- **WHEN** a client uploads files to the file upload endpoint
- **THEN** the response includes ingestion_id alongside run metadata
- **AND** ingestion_id matches the telemetry session emitted over WebSocket
