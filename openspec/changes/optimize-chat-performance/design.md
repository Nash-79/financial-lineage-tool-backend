# Design: Chat Performance Optimization

## Context
The chat API response time is currently 5-15+ seconds for typical queries. This is caused by sequential execution of:
1. Memory retrieval (embedding + vector search) ~300ms
2. Query embedding ~200ms
3. Vector search ~100ms
4. Graph search (per-word loop) ~100ms × N words
5. Lineage fetches (per-entity loop) ~200ms × N entities
6. LLM generation ~2-5s

Users expect sub-3-second responses for interactive chat. The current architecture blocks on each step unnecessarily.

## Goals
- Reduce P95 response time from ~10s to ~3s
- Reduce P50 response time from ~5s to ~1.5s
- Maintain response quality (no regression)
- Add streaming for perceived latency improvement

## Non-Goals
- Changing the LLM model or parameters
- Reducing context window size
- Caching full LLM responses (invalidation complexity)

## Decisions

### Decision 1: Parallel Execution with asyncio.gather()
**What**: Run embedding, vector search, and graph search concurrently instead of sequentially.

**Why**: These operations are independent - none depends on the output of another until the context building step.

**Implementation**:
```python
async def query(self, question: str, memory_context: str = "") -> dict:
    # Define independent operations
    async def do_vector_search():
        embedding = await self.ollama.embed(question, self.embedding_model)
        return await self.qdrant.search("code_chunks", embedding, limit=5)

    async def do_graph_search():
        words = [w for w in question.replace("_", " ").split() if len(w) > 3]
        return self.graph.find_by_names(words)  # New batch method

    # Execute in parallel
    code_results, graph_results = await asyncio.gather(
        do_vector_search(),
        do_graph_search(),
        return_exceptions=True
    )
```

### Decision 2: Redis Embedding Cache
**What**: Cache embeddings in Redis using content hash as key.

**Why**:
- Same queries are often repeated (especially in development/testing)
- Embedding is deterministic for same input
- Redis already connected in the application

**Implementation**:
```python
async def embed(self, text: str, model: str) -> list[float]:
    # Check cache first
    cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"
    if self.redis:
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

    # Generate and cache
    embedding = await self._call_ollama_embed(text, model)
    if self.redis:
        await self.redis.setex(cache_key, 86400, json.dumps(embedding))  # 24h TTL
    return embedding
```

### Decision 3: Batch Graph Queries
**What**: Replace word-by-word `find_by_name()` calls with single `find_by_names()` using Cypher `IN` clause.

**Why**: Each Neo4j round-trip adds ~50-100ms latency. Batching reduces N calls to 1.

**Implementation**:
```cypher
MATCH (n) WHERE n.name IN $names OR toLower(n.name) IN $lower_names
RETURN n LIMIT 10
```

### Decision 4: Optional Memory Retrieval
**What**: Add `skip_memory` flag to ChatRequest to bypass memory context retrieval.

**Why**:
- First message in session has no relevant history
- Some queries don't benefit from history
- Saves ~300ms when not needed

**Alternatives considered**:
- Auto-skip on first message: Requires session state tracking
- Remove memory entirely: Loses valuable context for follow-up questions

### Decision 5: SSE Streaming
**What**: Add streaming endpoint that sends partial responses as Server-Sent Events.

**Why**: Users see response start immediately instead of waiting for full generation.

**Implementation**:
- New endpoint: `POST /api/chat/deep/stream`
- Response type: `text/event-stream`
- Ollama `stream=True` mode

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Parallel errors harder to debug | Use `return_exceptions=True`, log individual failures |
| Cache invalidation on re-ingestion | Clear embedding cache when documents are re-indexed |
| Streaming complexity | Keep non-streaming endpoint as fallback |
| Memory pressure from caching | Set TTL (24h), monitor Redis memory |

## Migration Plan
1. Implement batch graph query (backward compatible)
2. Add embedding cache (transparent optimization)
3. Implement parallel execution (internal refactor)
4. Add skip_memory flag (additive, optional)
5. Add streaming endpoint (new endpoint, no breaking changes)

Rollback: All changes are additive or internal. No breaking changes to existing API.

## Open Questions
- Should streaming be the default for frontend? (Frontend team decision)
- Should we cache LLM responses for identical queries? (Deferred - invalidation complexity)
