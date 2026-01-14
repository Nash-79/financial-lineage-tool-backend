# Change: Optimize RAG Production Readiness

## Why

The current RAG (Retrieval-Augmented Generation) implementation has critical gaps preventing production deployment:

1. **No fallback strategy** - System fails when Ollama runs out of memory (OOM) on large queries
2. **Unoptimized retrieval** - Using default embeddings and HNSW settings without benchmarking
3. **No security controls** - All endpoints exposed without authentication, hardcoded credentials in config
4. **Limited observability** - Cannot diagnose performance issues or set SLOs
5. **Memory vulnerabilities** - Fixed 4096 context window causes crashes on complex lineage queries

Recent production testing revealed:
- 23% query failure rate due to Ollama OOM on queries >3000 tokens
- Average p95 latency of 4.2 seconds (no SLO defined)
- Zero cache hit rate on semantic queries (only exact hash matching)
- Security audit blocked deployment due to exposed Neo4j credentials

This change implements a comprehensive production-readiness strategy across 9 critical areas, prioritizing reliability, security, and performance.

## What Changes

### High Priority (Blocking Production)
- **ADDED** Hybrid inference routing with automatic fallback to Groq/OpenRouter when Ollama exhausted
- **ADDED** Graceful degradation mode: when LlamaIndex is degraded (Ollama/Qdrant unhealthy), system automatically routes to cloud-only inference (OpenRouter preferred for reliability)
- **ADDED** JWT authentication middleware with role-based access control
- **ADDED** Rate limiting per user/endpoint with configurable quotas
- **ADDED** Ollama health monitoring and adaptive context trimming
- **ADDED** Quantized model support (4-bit) and memory pressure detection
- **MODIFIED** Configuration management to require credentials via environment variables only
- **ADDED** Audit logging for ingestion, query, and admin operations

### Medium Priority (Quality & Scale)
- **ADDED** Embedding model benchmarking harness with Precision@k, Recall@k, MRR metrics
- **ADDED** Semantic query caching with similarity-based lookup (95% threshold)
- **ADDED** Batch embedding support to reduce Ollama API calls
- **ADDED** HNSW parameter tuning for Qdrant with dataset-specific configurations
- **ADDED** Prompt template library with hallucination safeguards and citation requirements
- **ADDED** Token budget enforcement with adaptive context selection
- **ADDED** Custom OpenTelemetry metrics for RAG operations (cache hit rates, OOM errors)
- **ADDED** SLO definitions for latency and availability
- **MODIFIED** LlamaIndex query engine to use `tree_summarize` for large contexts
- **ADDED** Frontend graph visualization with Cytoscape and virtual scrolling
- **ADDED** Fuzzy search and GraphML export capabilities

## Impact

### Affected Specs
- **llm-service** (MAJOR) - 7 new requirements, 2 modified
- **api-endpoints** (MAJOR) - 4 new requirements (auth, rate limiting)
- **logging** (MINOR) - 1 new requirement (audit logs)
- **deployment** (MINOR) - 1 modified requirement (security hardening)

### Affected Code
- `src/llm/` - New `inference_router.py`, `prompt_templates.py`, `remote_clients.py`
- `src/services/ollama_service.py` - Health checks, batch embeddings
- `src/services/qdrant_service.py` - HNSW tuning parameters
- `src/middleware/` - New `auth.py`, rate limiting
- `src/api/config.py` - Remove hardcoded credentials, add inference config
- `src/api/routers/` - Add authentication dependencies
- `src/utils/otel.py` - Custom RAG metrics
- `tests/benchmarks/` - New embedding quality tests
- Frontend: `src/components/LineageGraph.tsx`, `src/pages/Files.tsx`

### Breaking Changes
- **BREAKING**: All API endpoints require JWT authentication (except /health)
- **BREAKING**: NEO4J_PASSWORD must be set via environment variable (no default)
- **BREAKING**: ALLOWED_ORIGINS must be explicitly configured for production

### Migration Path
1. Set required environment variables: `NEO4J_PASSWORD`, `JWT_SECRET_KEY`, `ALLOWED_ORIGINS`
2. Generate API keys for existing service integrations
3. Update frontend to include JWT token in requests
4. Configure fallback inference provider (Groq or OpenRouter)
5. Run embedding benchmarks to validate model selection
6. Deploy with phased rollout using feature flags

### Risks
- **High**: Breaking changes require coordinated frontend/backend deployment
- **Medium**: Fallback inference adds cost (mitigated by local-first strategy)
- **Low**: Performance regression from auth overhead (estimated <5ms per request)

### Non-Goals
- Multi-tenancy support (future work)
- Advanced RBAC beyond user/admin roles (future work)
- Custom embedding model fine-tuning (use off-the-shelf models)
- Real-time reindexing (batch-only for now)
