## ADDED Requirements
### Requirement: Chat artifacts table for message-scoped data
The system SHALL store chat artifacts (graph data, metadata) in DuckDB for retrieval after conversation advancement.

#### Scenario: Chat artifacts schema
- **WHEN** DuckDB client initializes chat artifacts table
- **THEN** it creates table with schema:
  ```sql
  CREATE TABLE IF NOT EXISTS chat_artifacts (
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, message_id, artifact_type)
  )
  ```
- **AND** table supports UPSERT for artifact updates
- **AND** index on `created_at` for cleanup queries

#### Scenario: Store chat artifact
- **WHEN** chat service calls `store_chat_artifact(session_id, message_id, artifact_type, data)`
- **THEN** DuckDB client inserts or replaces artifact in `chat_artifacts` table
- **AND** `artifact_data` is serialized as JSON
- **AND** operation is idempotent (can safely retry)

#### Scenario: Retrieve chat artifact
- **WHEN** chat service calls `get_chat_artifact(session_id, message_id, artifact_type)`
- **THEN** DuckDB client returns artifact data as dict
- **AND** returns None if artifact doesn't exist
- **AND** retrieval is fast (indexed by primary key)

#### Scenario: Cleanup old chat artifacts
- **WHEN** system performs periodic cleanup
- **THEN** it deletes artifacts older than configurable retention period (default: 90 days)
- **AND** retention period is configurable via `CHAT_ARTIFACT_RETENTION_DAYS` environment variable
- **AND** cleanup respects snapshot intervals (doesn't break in-memory mode)
- **AND** cleanup is logged for monitoring
