## ADDED Requirements
### Requirement: Chat artifact persistence and retrieval
The system SHALL persist chat-scoped lineage graphs per message and provide retrieval endpoints for answer-specific graphs.

#### Scenario: Persist graph data with chat messages
- **WHEN** chat endpoint generates a response with `graph_data`
- **THEN** the system persists `graph_data` to `chat_artifacts` table in DuckDB
- **AND** artifact is keyed by `(session_id, message_id, artifact_type="graph")`
- **AND** artifact includes creation timestamp
- **AND** persistence happens asynchronously after response is sent

#### Scenario: Retrieve message-specific graph
- **WHEN** client requests `GET /api/chat/session/{session_id}/message/{message_id}/graph`
- **THEN** the system retrieves graph artifact from `chat_artifacts` table
- **AND** returns JSON with `{\"nodes\": [...], \"edges\": [...], \"metadata\": {...}}`
- **AND** response includes cache headers for client-side caching
- **AND** returns 404 if session_id/message_id combination doesn't exist

#### Scenario: Handle missing graph artifacts
- **WHEN** client requests graph for old message without persisted artifact
- **THEN** system returns 404 with clear error message
- **AND** error message suggests using current lineage page for historical analysis
- **AND** response includes `{"error": "Graph artifact not found", "message_id": "...", "session_id": "..."}`
