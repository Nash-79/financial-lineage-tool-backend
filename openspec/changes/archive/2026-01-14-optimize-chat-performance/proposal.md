# Change: Optimize Chat API Response Performance

**Status: IMPLEMENTED** (Backend complete, frontend integration pending)

## Why
The chat API (`/api/chat/deep`) takes too long to respond due to sequential operations in the query pipeline. Current flow executes embedding, vector search, graph search, lineage fetches, and LLM generation one after another, causing latency to stack up. Users experience 5-15+ second response times which degrades the interactive experience.

## What Changes
- [x] **Parallelize independent operations** using `asyncio.gather()` for embedding + graph search
- [x] **Add embedding caching** in Redis to skip Ollama calls for repeated queries
- [x] **Batch graph queries** to replace word-by-word Neo4j lookups with single Cypher query
- [x] **Make memory retrieval optional** with skip flag for first message or explicit opt-out
- [x] **Add streaming support** for `/deep` endpoint via Server-Sent Events (SSE)
- [x] **Fix `embed()` call signature** missing model parameter in `/semantic` endpoint

## Impact
- Affected specs: `llm-service`, `api-endpoints`
- Affected code:
  - `src/services/agent_service.py` - Parallel execution via `_parallel_search()`, `_get_lineage_info()`
  - `src/services/ollama_service.py` - Embedding caching with Redis, `generate_stream()` for SSE
  - `src/api/models/chat.py` - Added `skip_memory` flag to `ChatRequest`
  - `src/api/routers/chat.py` - Streaming endpoint `/api/chat/deep/stream`, fixed embed call
  - `src/knowledge_graph/neo4j_client.py` - Batch `find_by_names()` method
  - `src/api/main_local.py` - Pass Redis client to OllamaClient for caching

## Expected Performance Gains
| Optimization | Current | Expected | Improvement |
|--------------|---------|----------|-------------|
| Parallel embedding + graph search | Sequential (~800ms) | Parallel (~400ms) | ~50% |
| Embedding cache (repeated queries) | ~200ms/call | ~5ms (cache hit) | ~97% |
| Batched graph queries | ~100ms × N words | ~100ms total | ~80% |
| Optional memory retrieval | ~300ms always | 0ms when skipped | 100% |
| **Total (cold query)** | **~3-5s** | **~1.5-2.5s** | **~50%** |
| **Total (warm/cached)** | **~3-5s** | **~0.5-1s** | **~80%** |

## Implementation Summary

### Files Modified
| File | Changes |
|------|---------|
| `src/knowledge_graph/neo4j_client.py:210-268` | Added `find_by_names()` batch method |
| `src/services/agent_service.py:66-157` | Added `_parallel_search()` and `_get_lineage_info()` |
| `src/services/ollama_service.py:89-223` | Added Redis cache and `generate_stream()` |
| `src/api/models/chat.py:17-20` | Added `skip_memory` flag |
| `src/api/routers/chat.py:257-390` | Added `/api/chat/deep/stream` SSE endpoint |
| `src/api/routers/chat.py:147` | Fixed embed() call with model parameter |
| `src/api/main_local.py:107-129` | Reordered init to pass Redis to OllamaClient |

### Tests Added
| File | Coverage |
|------|----------|
| `tests/unit/services/test_chat_performance.py` | Unit tests for cache, batch, parallel |
| `tests/test_chat_endpoints.py` | Integration tests for new endpoints |

### Remaining Work
- [ ] Frontend SSE integration
- [ ] Performance benchmarks (4.3.x)
- [ ] Contract/Schemathesis tests (4.4.x)
- [ ] Additional documentation (5.2, 5.3, 6.x)
