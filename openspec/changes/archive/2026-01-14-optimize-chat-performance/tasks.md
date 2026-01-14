# Implementation Tasks

## 1. Core Performance Optimizations

- [x] 1.1 Add `find_by_names()` batch method to `neo4j_client.py` using Cypher `IN []` clause
- [x] 1.2 Refactor `agent_service.py` to parallelize vector search and graph search using `asyncio.gather()`
- [x] 1.3 Implement embedding cache in `ollama_service.py` using Redis with content hash keys
- [x] 1.4 Add `skip_memory` flag to `ChatRequest` model and handle in `/deep` endpoint

## 2. Streaming Support

- [x] 2.1 Add `/api/chat/deep/stream` SSE endpoint in `chat.py`
- [x] 2.2 Implement streaming response in `ollama_service.py` using `stream=True`
- [ ] 2.3 Update frontend to consume SSE stream (coordinate with frontend team)

## 3. Bug Fixes

- [x] 3.1 Fix `embed()` call in `/semantic` endpoint to include model parameter

## 4. Testing & Validation

### 4.1 Unit Tests
- [x] 4.1.1 Test `find_by_names()` batch method with various inputs (empty, single, multiple)
- [x] 4.1.2 Test embedding cache hit/miss scenarios
- [x] 4.1.3 Test embedding cache fallback when Redis unavailable
- [x] 4.1.4 Test `skip_memory` flag handling in ChatRequest
- [x] 4.1.5 Test streaming response chunking

### 4.2 Integration Tests
- [x] 4.2.1 Test parallel execution timing (verify concurrent operation)
- [x] 4.2.2 Test `/api/chat/deep` with and without `session_id`
- [x] 4.2.3 Test `/api/chat/deep` with `skip_memory=true`
- [x] 4.2.4 Test `/api/chat/deep/stream` SSE endpoint
- [x] 4.2.5 Test `/api/chat/title` endpoint
- [x] 4.2.6 Test `DELETE /api/chat/session/{session_id}` endpoint

### 4.3 Performance Tests
- [ ] 4.3.1 Create benchmark script for before/after comparison
- [ ] 4.3.2 Measure P50/P95/P99 latency for `/api/chat/deep`
- [ ] 4.3.3 Measure cache hit rate improvement
- [ ] 4.3.4 Verify no regression in response quality (manual spot check)

### 4.4 Contract Tests
- [ ] 4.4.1 Add Schemathesis tests for new endpoints
- [ ] 4.4.2 Verify OpenAPI schema includes new parameters
- [ ] 4.4.3 Add E2E smoke test for streaming endpoint

## 5. Backend Documentation

- [x] 5.1 Update `docs/api/API_REFERENCE.md` with:
  - New `/api/chat/deep/stream` SSE endpoint
  - New `skip_memory` parameter in ChatRequest
  - New `/api/chat/title` endpoint
  - New `DELETE /api/chat/session/{session_id}` endpoint
  - Updated ChatRequest/ChatResponse models with `session_id` and `graph_data`
- [ ] 5.2 Update `docs/architecture/LLAMAINDEX_RAG.md` with:
  - Parallel execution architecture diagram
  - Embedding cache flow with Redis
  - Performance optimization section
- [ ] 5.3 Add `docs/guides/CHAT_PERFORMANCE_TUNING.md` with:
  - Environment variables for performance tuning
  - Redis cache configuration
  - Streaming vs non-streaming trade-offs
  - Memory skip usage guidelines

## 6. Frontend Integration Documentation

- [ ] 6.1 Create `docs/integration/FRONTEND_CHAT_API.md` with:
  - Chat API endpoints overview
  - Request/response TypeScript interfaces
  - Session management with `session_id`
  - Memory context opt-out with `skip_memory`
  - Graph data visualization format
- [ ] 6.2 Document SSE streaming integration:
  - EventSource usage for `/api/chat/deep/stream`
  - Event types: `data`, `error`, `done`
  - Reconnection handling
  - Example React/TypeScript implementation
- [ ] 6.3 Document WebSocket dashboard integration:
  - Connection lifecycle
  - Message types and handlers
  - Reconnection strategy
