# Implementation Tasks: Optimize RAG Production Readiness

## Phase 1: Critical Reliability & Security (Weeks 1-2)

### 1. Hybrid Inference Strategy
- [x] 1.1 Create `src/llm/inference_router.py` with InferenceRouter class
- [x] 1.2 Add Ollama health check method (memory, model status)
- [x] 1.3 Implement query token estimation logic
- [x] 1.4 Create GroqClient in `src/llm/remote_clients.py`
- [x] 1.5 Create OpenRouterClient in `src/llm/remote_clients.py`
- [x] 1.6 Add routing decision logic (local vs fallback)
- [x] 1.7 Add fallback configuration to `config.py` (INFERENCE_FALLBACK_PROVIDER, API keys)
- [x] 1.8 Implement CircuitBreaker class with open/half-open/closed states
- [x] 1.9 Add 60-second cooldown timer for rate-limited providers
- [x] 1.10 Add rate limit error detection (HTTP 429 handling)
- [x] 1.11 Add circuit breaker metrics (state, open_count, half_open_attempts)
- [x] 1.12 Implement request cancellation support (AbortController integration)
- [x] 1.13 Add cleanup logic for cancelled LLM requests
- [x] 1.14 Update LlamaIndexService to use InferenceRouter
- [x] 1.15 Add fallback metrics (provider, success rate, circuit breaker state)
- [x] 1.16 Write unit tests for routing logic
- [x] 1.17 Write integration tests for OOM fallback
- [x] 1.18 Write tests for circuit breaker state transitions
- [x] 1.19 Write tests for request cancellation

### 2. Authentication & Authorization
- [x] 2.1 Create `src/middleware/auth.py` with JWT verification
- [x] 2.2 Add JWT_SECRET_KEY to config with validation
- [x] 2.3 Create /api/auth/login endpoint
- [x] 2.4 Create /api/auth/token/refresh endpoint
- [x] 2.5 Add authentication dependency to protected routes
- [x] 2.6 Add API key authentication for service accounts
- [x] 2.7 Update frontend API client to include Bearer token
- [x] 2.8 Write auth middleware tests
- [x] 2.9 Document authentication flow in docs/api/AUTHENTICATION.md

### 3. Rate Limiting
- [x] 3.1 Add slowapi to requirements.txt
- [x] 3.2 Create rate limiter instance in main_local.py
- [x] 3.3 Add per-user rate limiting (Redis-backed)
- [x] 3.4 Add per-endpoint rate limits (configurable via env vars)
- [x] 3.5 Add rate limit headers to responses
- [x] 3.6 Add rate limit exceeded handler
- [x] 3.7 Write rate limiting tests
- [x] 3.8 Document rate limits in API_REFERENCE.md

### 4. Secure Configuration Management
- [x] 4.1 Remove hardcoded NEO4J_PASSWORD from config.py
- [x] 4.2 Add production mode validation (ENVIRONMENT=production)
- [x] 4.3 Require JWT_SECRET_KEY, ALLOWED_ORIGINS in production
- [x] 4.4 Add CORS origin strict validation
- [x] 4.5 Add credential masking to logging
- [x] 4.6 Update deployment guide with required env vars
- [x] 4.7 Create .env.example with all required variables

### 5. Ollama Memory Mitigation
- [x] 5.1 Add OLLAMA_USE_QUANTIZED config flag
- [x] 5.2 Update model selection to support quantized variants
- [x] 5.3 Implement AdaptiveContextManager class
# Implementation Tasks: Optimize RAG Production Readiness

## Phase 1: Critical Reliability & Security (Weeks 1-2)

### 1. Hybrid Inference Strategy
- [x] 1.1 Create `src/llm/inference_router.py` with InferenceRouter class
- [x] 1.2 Add Ollama health check method (memory, model status)
- [x] 1.3 Implement query token estimation logic
- [x] 1.4 Create GroqClient in `src/llm/remote_clients.py`
- [x] 1.5 Create OpenRouterClient in `src/llm/remote_clients.py`
- [x] 1.6 Add routing decision logic (local vs fallback)
- [x] 1.7 Add fallback configuration to `config.py` (INFERENCE_FALLBACK_PROVIDER, API keys)
- [x] 1.8 Implement CircuitBreaker class with open/half-open/closed states
- [x] 1.9 Add 60-second cooldown timer for rate-limited providers
- [x] 1.10 Add rate limit error detection (HTTP 429 handling)
- [x] 1.11 Add circuit breaker metrics (state, open_count, half_open_attempts)
- [x] 1.12 Implement request cancellation support (AbortController integration)
- [x] 1.13 Add cleanup logic for cancelled LLM requests
- [x] 1.14 Update LlamaIndexService to use InferenceRouter
- [x] 1.15 Add fallback metrics (provider, success rate, circuit breaker state)
- [x] 1.16 Write unit tests for routing logic
- [x] 1.17 Write integration tests for OOM fallback
- [x] 1.18 Write tests for circuit breaker state transitions
- [x] 1.19 Write tests for request cancellation

### 2. Authentication & Authorization
- [x] 2.1 Create `src/middleware/auth.py` with JWT verification
- [x] 2.2 Add JWT_SECRET_KEY to config with validation
- [x] 2.3 Create /api/auth/login endpoint
- [x] 2.4 Create /api/auth/token/refresh endpoint
- [x] 2.5 Add authentication dependency to protected routes
- [x] 2.6 Add API key authentication for service accounts
- [x] 2.7 Update frontend API client to include Bearer token
- [x] 2.8 Write auth middleware tests
- [x] 2.9 Document authentication flow in docs/api/AUTHENTICATION.md

### 3. Rate Limiting
- [x] 3.1 Add slowapi to requirements.txt
- [x] 3.2 Create rate limiter instance in main_local.py
- [x] 3.3 Add per-user rate limiting (Redis-backed)
- [x] 3.4 Add per-endpoint rate limits (configurable via env vars)
- [x] 3.5 Add rate limit headers to responses
- [x] 3.6 Add rate limit exceeded handler
- [x] 3.7 Write rate limiting tests
- [x] 3.8 Document rate limits in API_REFERENCE.md

### 4. Secure Configuration Management
- [x] 4.1 Remove hardcoded NEO4J_PASSWORD from config.py
- [x] 4.2 Add production mode validation (ENVIRONMENT=production)
- [x] 4.3 Require JWT_SECRET_KEY, ALLOWED_ORIGINS in production
- [x] 4.4 Add CORS origin strict validation
- [x] 4.5 Add credential masking to logging
- [x] 4.6 Update deployment guide with required env vars
- [x] 4.7 Create .env.example with all required variables

### 5. Ollama Memory Mitigation
- [x] 5.1 Add OLLAMA_USE_QUANTIZED config flag
- [x] 5.2 Update model selection to support quantized variants
- [x] 5.3 Implement AdaptiveContextManager class
- [x] 5.4 Add query token estimation before generation
- [x] 5.5 Implement context trimming by relevance score
- [x] 5.6 Update query engine to use tree_summarize for top_k > 10
- [x] 5.7 Add context adjustment logging
- [x] 5.8 Write memory mitigation tests

### 6. Audit Logging
- [x] 6.1 Create `src/utils/audit_logger.py` with AuditLogger class
- [x] 6.2 Add audit log storage (PostgreSQL table or file)
- [x] 6.3 Log ingestion events (file upload, project_id)
- [x] 6.4 Log query events (query hash, user_id, latency)
- [x] 6.5 Log admin actions (delete, modify permissions)
- [x] 6.6 Add PII redaction for query logs
- [x] 6.7 Implement log retention policy
- [x] 6.8 Write audit log tests

## Phase 2: Quality & Optimization (Weeks 3-4)

### 7. Embedding Model Benchmarking
- [x] 8.4 Add answer accuracy evaluation (correct/incorrect)
- [x] 8.5 Add citation quality scoring (% claims with valid sources)
- [x] 8.6 Add hallucination detection (manual review + patterns)
- [x] 8.7 Add completeness scoring (recall of relevant entities)
- [x] 8.8 Add latency measurement (TTFT and total time)
- [x] 8.9 Add context utilization tracking
- [x] 8.10 Create benchmark CLI script for all free models
- [ ] 8.11 Run benchmarks for Ollama (llama3.1:8b, quantized variant)
- [ ] 8.12 Run benchmarks for Groq (llama-3.1-70b, llama-3.1-8b, mixtral-8x7b)
- [ ] 8.13 Run benchmarks for OpenRouter (llama-3.1-8b:free, gemma-2-9b:free)
- [ ] 8.14 Generate markdown comparison report with recommendations
- [x] 8.15 Document LLM benchmark methodology in docs/benchmarks/LLM_METHODOLOGY.md
- [ ] 8.16 Add benchmark results to frontend model selector (badges)

### 9. Semantic Query Caching
- [x] 9.1 Create SemanticQueryCache class in llamaindex_service.py
- [x] 9.2 Create query_cache Qdrant collection
- [x] 9.3 Store query embeddings with Redis cache key
- [x] 9.4 Implement similarity-based lookup (threshold 0.95)
- [x] 9.5 Add cache invalidation on reindex
- [x] 9.6 Track semantic cache hit rate
- [x] 9.7 Write semantic cache tests

### 10. Batch Embedding Support
- [x] 10.1 Add embed_batch method to OllamaClient
- [x] 10.2 Implement parallel cache lookup for batch
- [x] 10.3 Add batch size splitting (max 50 per batch)
- [x] 10.4 Add cache warming on startup (optional, USE_CACHE_WARMING flag)
- [x] 10.5 Optimize batch performance tests

### 11. HNSW Index Tuning
- [x] 11.1 Add QDRANT_HNSW_EF_CONSTRUCT config
- [x] 11.2 Add QDRANT_HNSW_M config
- [x] 11.3 Update create_collection to accept HNSW params
- [x] 11.4 Create IndexManager class for maintenance
- [x] 11.5 Add collection statistics endpoint
- [x] 11.6 Document HNSW tuning guide in docs/operations/QDRANT_TUNING.md

### 12. Prompt Template Management
- [ ] 12.1 Create `src/llm/prompt_templates.py` with PromptTemplates class
- [ ] 12.2 Define LINEAGE_QUERY template with citation requirements
- [ ] 12.3 Define GRAPH_QUERY template
- [ ] 12.4 Create TokenBudgetManager class
- [ ] 12.5 Implement token budget enforcement
- [ ] 12.6 Create ProjectContextManager for relevant context selection
- [ ] 12.7 Update RAG query to use templates
- [ ] 12.8 Write prompt template tests

### 13. Custom OpenTelemetry Metrics
- [ ] 13.1 Add RAG query latency histogram to otel.py
- [ ] 13.2 Add cache hit rate gauge
- [ ] 13.3 Add Ollama OOM error counter
- [ ] 13.4 Add inference routing metrics
- [ ] 13.5 Add SLO compliance metrics
- [ ] 13.6 Update LlamaIndexService to emit metrics
- [ ] 13.7 Create SigNoz dashboard JSON config
- [ ] 13.8 Document metrics in docs/observability/METRICS.md

## Phase 3: Scale & Polish (Weeks 5-6)

### 14. SLO Definitions & Monitoring
- [ ] 14.1 Create docs/operations/SLOS.md with latency targets
- [ ] 14.2 Add SLO tracking to health endpoint
- [ ] 14.3 Create alerting rules for SigNoz (signoz-alerts.yaml)
- [ ] 14.4 Implement health check dashboard endpoint
- [ ] 14.5 Document SLO compliance reporting

### 15. Frontend Graph Visualization
- [ ] 15.1 Add cytoscape and react-cytoscapejs to package.json
- [ ] 15.2 Create src/components/LineageGraph.tsx
- [ ] 15.3 Implement graph rendering with Cytoscape
- [ ] 15.4 Add node/edge styling by entity type
- [ ] 15.5 Add interactive zoom and pan
- [ ] 15.6 Integrate graph component in Files page

### 16. Frontend Virtual Scrolling
- [ ] 16.1 Add @tanstack/react-virtual to package.json
- [ ] 16.2 Create VirtualFileTree component
- [ ] 16.3 Replace file tree with virtual scrolling
- [ ] 16.4 Test performance with 10k+ files

### 17. Frontend Fuzzy Search & Export
- [ ] 17.1 Add fuse.js to package.json
- [ ] 17.2 Implement fuzzy search on file names
- [ ] 17.3 Add GraphML export function
- [ ] 17.4 Add CSV export for lineage data
- [ ] 17.5 Add export button to UI

### 18. Frontend Model Selector & Request Control
- [ ] 18.1 Create ModelSelector component in src/components/
- [ ] 18.2 Add dropdown with free model options (Ollama, Groq, OpenRouter)
- [ ] 18.3 Display model metadata (context window, speed, badges)
- [ ] 18.4 Store selected model in localStorage
- [ ] 18.5 Pass selected model to chat API endpoints
- [ ] 18.6 Add model selector to chat interface
- [ ] 18.7 Add inference mode selector (local-first, cloud-only, local-only)
- [ ] 18.8 Display benchmark results badges (⭐ Best Quality, 🚀 Fastest, 🔒 Most Private)
- [ ] 18.9 Add "Stop Generation" button during active inference
- [ ] 18.10 Implement AbortController for request cancellation
- [ ] 18.11 Add visual feedback for cancelled requests
- [ ] 18.12 Add loading state with progress indicator
- [ ] 18.13 Display rate limit errors with clear messaging
- [ ] 18.14 Show estimated wait time when circuit breaker opens
- [ ] 18.15 Add retry button for failed requests

## Phase 4: Testing & Documentation (Week 6)

### 19. Integration Tests
- [ ] 19.1 Write end-to-end auth flow tests
- [ ] 19.2 Write fallback inference tests
- [ ] 19.3 Write rate limiting integration tests
- [ ] 19.4 Write audit log integration tests
- [ ] 19.5 Write cache invalidation tests
- [ ] 19.6 Write model selector integration tests

### 20. Documentation Updates
- [ ] 20.1 Update API_REFERENCE.md with auth requirements
- [ ] 20.2 Update DEPLOYMENT_GUIDE.md with production checklist
- [ ] 20.3 Create SECURITY.md with best practices
- [ ] 20.4 Update LLAMAINDEX_RAG.md with new features
- [ ] 20.5 Create TROUBLESHOOTING.md for common issues
- [ ] 20.6 Update README.md with breaking changes notice
- [ ] 20.7 Document free model selection and benchmarking in user guide

## Phase 5: Deployment & Validation (Week 7)

### 21. Deployment Preparation
- [ ] 21.1 Create production environment config template
- [ ] 21.2 Update docker-compose.yml with new env vars
- [ ] 21.3 Create migration script for breaking changes
- [ ] 21.4 Set up staging environment for testing
- [ ] 21.5 Run full benchmark suite on staging (embedding + LLM)

### 22. Phased Rollout
- [ ] 22.1 Deploy Phase 1 (auth, security) to staging
- [ ] 22.2 Validate auth flow and rate limiting
- [ ] 22.3 Deploy Phase 2 (optimization) to staging
- [ ] 22.4 Run performance benchmarks
- [ ] 22.5 Deploy to production with feature flags
- [ ] 22.6 Monitor metrics for 48 hours
- [ ] 22.7 Enable all features in production

### 23. Post-Deployment Validation
- [ ] 23.1 Validate SLO compliance (p95 < 2000ms)
- [ ] 23.2 Validate cache hit rates (> 40%)
- [ ] 23.3 Validate zero OOM errors
- [ ] 23.4 Validate audit logs are being written
- [ ] 23.5 Run security scan (OWASP ZAP or similar)
- [ ] 23.6 Validate frontend model selector working correctly
- [ ] 23.7 Document lessons learned
