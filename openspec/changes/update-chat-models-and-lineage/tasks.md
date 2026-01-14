## 1. Update Free-Tier Models and Routing
- [x] 1.1 Add `qwen/qwen3-4b:free` to `FREE_TIER_MODELS` list in `src/api/config.py`
- [x] 1.2 Update chat endpoint primary/secondary/tertiary model configuration:
  - [x] `/api/chat/deep`: deepseek-r1-0528 → devstral-2512 → gemini-2.0-flash-exp
  - [x] `/api/chat/graph`: devstral-2512 → deepseek-r1-0528 → gemini-2.0-flash-exp
  - [x] `/api/chat/semantic`: gemini-2.0-flash-exp → qwen3-4b → mistral-7b-instruct
  - [x] `/api/chat/text`: gemini-2.0-flash-exp → mistral-7b-instruct → qwen3-4b
- [x] 1.3 Update `_DEFAULT_FREE_TIER_MODELS` documentation with OpenRouter URLs and context sizes

## 2. Add Chat Artifacts Persistence
- [x] 2.1 Add `chat_artifacts` table to DuckDB schema in `src/storage/duckdb_client.py`
  - Columns: `session_id TEXT, message_id TEXT, artifact_type TEXT, artifact_data JSON, created_at TIMESTAMP`
  - Primary key: `(session_id, message_id, artifact_type)`
- [x] 2.2 Add `store_chat_artifact()` method to DuckDB client
- [x] 2.3 Add `get_chat_artifact()` method to DuckDB client
- [x] 2.4 Update `chat_service.py` to persist `graph_data` after generating response

## 3. Add Chat Artifact Retrieval Endpoint
- [x] 3.1 Create `GET /api/chat/session/{session_id}/message/{message_id}/graph` endpoint in `src/api/routers/chat.py`
- [x] 3.2 Add request/response models for graph retrieval
- [x] 3.3 Add 404 handling for missing artifacts

## 4. Documentation and Verification
- [x] 4.1 Update API docs for new graph retrieval endpoint (api-endpoints spec updated)
- [x] 4.2 Add docstring comments with OpenRouter model URLs and capabilities (config.py)
- [x] 4.3 Document runtime model verification pattern in `llm-service` spec (for future implementation)
- [x] 4.4 Update openspec main specs (api-endpoints, llm-service, data-organization) with implementation details

## 5. Testing
- [x] 5.1 Add unit tests for chat artifact persistence (DuckDB client methods)
- [x] 5.2 Add unit tests for chat endpoint model routing order (verify primary/secondary/tertiary per endpoint)
- [ ] 5.3 Add integration test for `/api/chat/session/{session_id}/message/{message_id}/graph` endpoint
- [ ] 5.4 Manual verification: send chat request, verify graph_data is persisted, retrieve via new endpoint

## 6. Validation
- [x] 6.1 Run `pytest tests/unit/storage -k chat_artifact -v`
- [x] 6.2 Run `pytest tests/unit/llm -k model_routing -v`
- [ ] 6.3 Run `pytest tests/integration/api -k chat_graph -v`
- [ ] 6.4 Manually test chat endpoints with new routing and verify fallback behavior
