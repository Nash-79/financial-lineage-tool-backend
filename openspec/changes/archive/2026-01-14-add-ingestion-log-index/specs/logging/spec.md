## ADDED Requirements
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
