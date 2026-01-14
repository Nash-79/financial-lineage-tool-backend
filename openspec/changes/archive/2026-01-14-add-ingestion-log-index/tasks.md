## 1. Implementation
- [x] 1.1 Add ingestion log index metadata (per run) and keep it updated on completion.
- [x] 1.2 Add /api/v1/ingestion/logs list endpoint with filters (project_id, source, status), recent-first sorting, and a /api/v1/ingestion/logs/{ingestion_id} detail endpoint.
- [x] 1.3 Emit ingestion stage events (parsing, chunking, embedding, indexing, LLM) with start/complete/failed status.
- [x] 1.4 Add unit tests for log list endpoint and stage telemetry emission.
- [x] 1.5 Update API docs for the new list endpoint.

## 2. Validation
- [x] 2.1 python -m pytest tests/unit/api -q
