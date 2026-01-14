# Design Document: RAG Production Readiness Optimization

## Context

The Financial Lineage Tool's RAG pipeline currently runs exclusively on local Ollama, which works well for development but has critical production limitations:

**Technical Constraints:**
- Ollama runs on host machine with limited memory (typically 16GB)
- llama3.1:8b model requires ~8GB RAM, leaving ~8GB for context processing
- Context window of 4096 tokens can handle most queries but fails on complex lineage traversals
- No redundancy if Ollama crashes or runs OOM

**Business Requirements:**
- Production deployment blocked by security audit (exposed credentials, no auth)
- Need 99.5% availability SLA
- Need predictable performance (p95 < 2s latency)
- Must support queries up to 10k tokens (complex multi-hop lineage)

**Stakeholders:**
- Engineering: Need reliability and observability
- Security: Need authentication, audit logs, credential management
- Product: Need fast queries and good UX

## Goals / Non-Goals

### Goals
1. **Reliability**: Zero OOM crashes, automatic fallback on Ollama failure
2. **Security**: Production-grade auth, no exposed credentials, audit logging
3. **Performance**: Optimize cache hit rates, retrieval quality, reduce latency
4. **Observability**: Custom metrics, SLO tracking, alerting
5. **Scale**: Support 1000+ users, 100k+ documents, 10k tokens per query
6. **Cost Control**: Support 100% free model options (Groq, OpenRouter free tier)
7. **User Choice**: Allow frontend model selection for users who prefer cloud-only

### Non-Goals
- Multi-tenancy (single-tenant per deployment for now)
- Custom model fine-tuning (use off-the-shelf models)
- Real-time reindexing (batch updates sufficient)
- Advanced RBAC (user/admin roles only)
- Multi-region deployment (single-region for v1)
- Paid model support (only free models in scope)

## Decisions

### Decision 1: Hybrid Inference Strategy with User-Selectable Free Models

**What:**
Support three inference modes with frontend model selector:
1. **Local-first (default)**: Ollama with automatic fallback to Groq/OpenRouter free tier
2. **Cloud-only**: Skip Ollama, use Groq/OpenRouter free models directly
3. **Local-only**: Ollama only, no fallback (dev/privacy mode)

**Why:**
- **Cost**: All modes use 100% free models (no API costs)
- **Choice**: Users without local GPU can use cloud-only mode
- **Performance**: Cloud-only bypasses Ollama setup complexity
- **Privacy**: Local-only for sensitive data
- **Reliability**: Graceful degradation with automatic fallback

**Free Model Catalog:**

| Provider | Model | Context | Speed | Notes |
|----------|-------|---------|-------|-------|
| **Ollama** | llama3.1:8b | 4k-32k | Fast | Local, free |
| **Ollama** | llama3.1:8b-q4_0 | 4k-32k | Fast | 50% less memory |
| **Groq** | llama-3.1-70b-versatile | 8k | Very fast | Free tier: 30 req/min |
| **Groq** | llama-3.1-8b-instant | 8k | Fastest | Free tier: 30 req/min |
| **Groq** | mixtral-8x7b-32768 | 32k | Fast | Free tier: 30 req/min |
| **OpenRouter** | meta-llama/llama-3.1-8b-instruct:free | 8k | Medium | Free tier |
| **OpenRouter** | google/gemma-2-9b-it:free | 8k | Medium | Free tier |

**Alternatives Considered:**
1. **Paid models only** - Rejected: Cost prohibitive for open-source tool
2. **Multiple Ollama instances** - Rejected: Complex orchestration, still limited by host memory
3. **No user choice** - Rejected: Limits accessibility for users without local GPU

**Implementation:**
```python
class InferenceRouter:
    def __init__(self, user_preference: str = "local-first"):
        self.mode = user_preference  # local-first, cloud-only, local-only
        self.ollama = OllamaClient()
        self.groq = GroqClient()
        self.openrouter = OpenRouterClient()

    async def route_request(self, prompt: str, user_selected_model: str = None) -> str:
        tokens = estimate_tokens(prompt)

        # Honor user-selected model if provided
        if user_selected_model:
            return await self.generate_with_model(prompt, user_selected_model)

        # Mode-based routing
        if self.mode == "cloud-only":
            return await self.groq.generate(prompt, "llama-3.1-8b-instant")

        elif self.mode == "local-only":
            return await self.ollama.generate(prompt, "llama3.1:8b")

        else:  # local-first (default)
            health = await self.ollama.check_health()

            if health.healthy and tokens < 3000:
                try:
                    return await self.ollama.generate(prompt)
                except OOMError:
                    logger.warning("Ollama OOM, falling back to Groq")
                    return await self.groq.generate(prompt, "llama-3.1-70b-versatile")
            else:
                return await self.groq.generate(prompt, "llama-3.1-70b-versatile")
```

### Decision 2: JWT Authentication with API Keys for Services

**What:**
- User authentication: JWT tokens (24h expiration)
- Service-to-service: API keys (rotatable, stored in DB)
- All endpoints except /health require auth

**Why:**
- **Standard**: JWT is industry standard for stateless auth
- **Scalability**: No session storage required
- **Flexibility**: API keys for CI/CD, integrations

**Alternatives Considered:**
1. **OAuth2 only** - Rejected: Overkill for single-tenant, slower to implement
2. **Session-based** - Rejected: Doesn't scale, requires sticky sessions
3. **No auth** - Rejected: Security audit requirement

**Implementation:**
- JWT library: PyJWT
- Secret rotation: Manual for v1, automated in v2
- Token payload: `{user_id, role, exp}`

### Decision 3: Semantic Query Caching (Similarity-Based)

**What:**
Cache query results using similarity matching (threshold 0.95) in addition to exact hash matching.

**Why:**
- Users often ask similar questions ("show lineage of customer_id" vs "what's the lineage for customer_id")
- Exact hash matching has ~10% hit rate, similarity-based can reach 40-50%
- Reduces load on Ollama and improves latency

**Alternatives Considered:**
1. **Exact match only** - Rejected: Low hit rate
2. **LLM-based query normalization** - Rejected: Adds latency, complexity
3. **No caching** - Rejected: Poor performance

**Implementation:**
- Store query embedding in Qdrant `query_cache` collection
- On new query, search for similar queries with score >= 0.95
- If found, return cached result from Redis
- Cache invalidation: Clear all on reindex event

### Decision 4: Prompt Templates with Token Budget Enforcement

**What:**
Centralized prompt templates with strict token budget allocation:
- System prompt: 5%
- Project context: 10%
- Retrieved chunks: 60%
- User question: 5%
- Response buffer: 20%

**Why:**
- **Predictability**: Never exceed context window
- **Quality**: Explicit citation requirements reduce hallucinations
- **Maintainability**: Templates easier to test and update than inline strings

**Alternatives Considered:**
1. **Dynamic allocation** - Rejected: Too complex, hard to predict
2. **No budget** - Rejected: Causes OOM on large contexts
3. **Fixed token limits** - Rejected: Wastes context on small queries

**Implementation:**
```python
class TokenBudgetManager:
    def allocate(self, context: str, question: str) -> str:
        max_tokens = CONTEXT_WINDOW * 0.6  # 60% for retrieval
        chunks = rank_by_relevance(context)

        selected = []
        token_count = 0
        for chunk in chunks:
            if token_count + chunk.tokens > max_tokens:
                break
            selected.append(chunk)
            token_count += chunk.tokens

        return format_template(selected, question)
```

### Decision 5: Quantized Models for Memory Efficiency

**What:**
Use 4-bit quantized models (llama3.1:8b-q4_0) when OLLAMA_USE_QUANTIZED=true.

**Why:**
- **Memory**: ~50% reduction (8GB → 4GB)
- **Quality**: Minimal accuracy loss (<2% on benchmarks)
- **Speed**: Slightly faster inference due to reduced memory bandwidth

**Alternatives Considered:**
1. **8-bit quantization** - Rejected: Only 25% savings, not worth it
2. **No quantization** - Rejected: Higher OOM risk
3. **Smaller models (7b)** - Rejected: Noticeable quality drop

**Implementation:**
- Environment flag: OLLAMA_USE_QUANTIZED=true
- Model selection: `llama3.1:8b-q4_0` vs `llama3.1:8b`
- Validation: Check quantized model exists on startup

### Decision 6: Free Embedding Model Benchmarking and Selection

**What:**
Benchmark only free Ollama embedding models on SQL lineage retrieval tasks and auto-select the best performer:

| Provider | Model | Dimensions | Size | Cost | Availability |
|----------|-------|------------|------|------|--------------|
| **Ollama** | nomic-embed-text | 768 | 274MB | Free | Local only |
| **Ollama** | all-minilm-l6-v2 | 384 | 80MB | Free | Local only |
| **Ollama** | bge-small-en-v1.5 | 384 | 133MB | Free | Local only |
| **Groq** | N/A | - | - | N/A | No embedding models offered |
| **OpenRouter** | N/A | - | - | N/A | Free tier excludes embeddings |

**Benchmark Criteria:**
- **Precision@5, Recall@5, MRR** on 20+ curated SQL lineage queries
- **Latency** (embeddings per second)
- **Memory footprint**
- **Retrieval quality** on technical/SQL content

**Selection Strategy:**
- Run benchmark suite on first ingestion (optional, enabled with BENCHMARK_EMBEDDINGS=true)
- Store results in `docs/benchmarks/EMBEDDING_RESULTS_[date].md`
- Auto-select model with highest F1 score (balance precision/recall)
- User can override with EMBEDDING_MODEL env var
- Default to nomic-embed-text if no benchmark run

**Why:**
- **Cost**: Only free models available (Groq/OpenRouter don't offer free embedding APIs)
- **Quality**: Empirical data beats assumptions
- **Simplicity**: Ollama-only for embeddings (cloud providers don't offer comparable free tier)
- **Local-first**: Embedding models must run locally, no cloud fallback option

**Alternatives Considered:**
1. **Paid embeddings** (OpenAI text-embedding-3-small at $0.02/1M tokens) - Rejected: Cost prohibitive for open-source tool
2. **Manual selection** - Rejected: No data-driven decision
3. **Skip benchmarking** - Rejected: May use suboptimal model
4. **Cloud embedding providers** - Rejected: No free tier options available

**Expected Outcome:**
Based on preliminary tests, `nomic-embed-text` likely wins due to:
- Higher dimensions (768 vs 384) captures more semantic information
- Trained on diverse text including code and technical documentation
- Good performance on technical/SQL content in initial testing
- Recommended by Ollama community for code retrieval tasks

### Decision 7: LLM Text Generation Quality Benchmarking

**What:**
Benchmark all free LLM models (Ollama, Groq, OpenRouter) on SQL lineage question-answering quality and provide recommendations:

| Provider | Model | Context | Speed | Availability |
|----------|-------|---------|-------|--------------|
| **Ollama** | llama3.1:8b | 4k-32k | Fast | Local only |
| **Ollama** | llama3.1:8b-q4_0 | 4k-32k | Fast | Local only (quantized) |
| **Groq** | llama-3.1-70b-versatile | 8k | Very fast | Free tier: 30 req/min |
| **Groq** | llama-3.1-8b-instant | 8k | Fastest | Free tier: 30 req/min |
| **Groq** | mixtral-8x7b-32768 | 32k | Fast | Free tier: 30 req/min |
| **OpenRouter** | meta-llama/llama-3.1-8b-instruct:free | 8k | Medium | Free tier |
| **OpenRouter** | google/gemma-2-9b-it:free | 8k | Medium | Free tier |

**Benchmark Criteria:**
- **Answer Accuracy**: Correct lineage relationships identified (binary: correct/incorrect)
- **Citation Quality**: Source references included and accurate (% of claims with valid [file:line] citations)
- **Hallucination Rate**: Incorrect or fabricated information (% of responses with hallucinations)
- **Completeness**: All relevant entities mentioned (recall score)
- **Latency**: Time to first token and total generation time
- **Context Utilization**: Ability to use full context window effectively

**Test Dataset:**
- 20+ curated SQL lineage questions covering:
  - Simple table-to-table lineage (1-hop)
  - Multi-hop column lineage (3+ hops)
  - CTE and subquery dependencies
  - Stored procedure analysis
  - Cross-schema references
- Each question has labeled ground truth answers
- Questions vary in complexity and context size

**Selection Strategy:**
- Run benchmark suite manually (not automated on first ingestion)
- Store results in `docs/benchmarks/LLM_RESULTS_[date].md`
- Provide recommendation based on quality-latency-cost tradeoff:
  - **Best Quality**: Highest accuracy and lowest hallucination rate
  - **Best Speed**: Lowest latency while maintaining acceptable accuracy (>85%)
  - **Best Balanced**: Optimal F1 score (precision + recall) with reasonable latency
- User can override default model via frontend selector or INFERENCE_DEFAULT_MODEL env var

**Why:**
- **Cost**: All models are free (no API costs)
- **Quality**: SQL lineage queries are domain-specific; generic benchmarks don't predict performance
- **Transparency**: Users can see which model works best for their use case
- **Informed Choice**: Frontend model selector should show benchmark results to help users decide

**Alternatives Considered:**
1. **No benchmarking, use llama-3.1-70b by default** - Rejected: May not be best for SQL lineage, no data-driven decision
2. **Automatic model selection** - Rejected: Different users have different priorities (speed vs quality)
3. **Only benchmark Ollama models** - Rejected: Cloud models may outperform local, users should know
4. **Use third-party benchmarks (MMLU, HumanEval)** - Rejected: Not specific to SQL lineage domain

**Expected Outcome:**
Based on model characteristics, likely results:
- **llama-3.1-70b-versatile (Groq)**: Highest quality, best for complex multi-hop queries, moderate speed
- **llama-3.1-8b-instant (Groq)**: Fastest, good for simple queries, may struggle with complex lineage
- **mixtral-8x7b-32768 (Groq)**: Best for large context (>4k tokens), good balance of speed and quality
- **llama3.1:8b (Ollama)**: Good quality, unlimited usage, no rate limits, privacy-first
- **gemma-2-9b-it:free (OpenRouter)**: Untested, may have different strengths

**Implementation:**
- CLI command: `python -m tests.benchmarks.benchmark_llm --models all --output docs/benchmarks/`
- Results displayed in frontend model selector as badges (e.g., "Best Quality ⭐", "Fastest 🚀", "Most Private 🔒")

### Decision 8: Circuit Breaker and Request Cancellation

**What:**
Implement circuit breaker pattern for rate-limited providers and support request cancellation from the frontend.

**Circuit Breaker States:**
1. **Closed (Normal)**: All requests pass through to provider
2. **Open (Tripped)**: All requests fail-fast for 60 seconds after rate limit error
3. **Half-Open (Testing)**: After cooldown, allow 1 test request to check if provider recovered

**Request Cancellation:**
- Frontend sends AbortController signal when user clicks "Stop Generation"
- Backend immediately terminates active LLM streaming connection
- Cleanup: Cancel Ollama/Groq/OpenRouter API requests, discard partial responses
- Return 499 Client Closed Request status

**Why:**
- **Circuit Breaker**: Prevents cascading failures and wasted API calls when provider is rate-limited
- **Request Cancellation**: Improves UX when users realize query needs refinement, saves compute resources
- **Explicit Behavior**: Clear error messages ("Rate limit exceeded, trying alternate provider") with estimated wait time
- **Resource Cleanup**: Prevents orphaned requests and memory leaks

**Alternatives Considered:**
1. **No circuit breaker** - Rejected: Wastes API calls and degrades UX with repeated failures
2. **Longer cooldown (5 minutes)** - Rejected: Too long, users expect faster recovery
3. **No request cancellation** - Rejected: Poor UX, wastes compute on unwanted responses
4. **Client-side only cancellation** - Rejected: Doesn't clean up backend resources

**Implementation:**
```python
class CircuitBreaker:
    def __init__(self, cooldown_seconds: int = 60):
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.last_failure_time = None
        self.cooldown_seconds = cooldown_seconds

    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.cooldown_seconds:
                self.state = "half_open"
            else:
                raise CircuitBreakerOpenError("Rate limit cooldown in progress")

        try:
            result = await func(*args, **kwargs)
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except RateLimitError:
            self.failure_count += 1
            self.last_failure_time = time.time()
            self.state = "open"
            raise
```

**Frontend Implementation:**
```typescript
const abortController = new AbortController();

async function sendQuery(query: string) {
  try {
    const response = await fetch('/api/chat/deep', {
      method: 'POST',
      body: JSON.stringify({ query }),
      signal: abortController.signal
    });
    // Handle response...
  } catch (error) {
    if (error.name === 'AbortError') {
      console.log('Request cancelled by user');
    }
  }
}

function stopGeneration() {
  abortController.abort();
  setIsGenerating(false);
  setStatusMessage('Generation stopped');
}
```

### Decision 9: HNSW Tuning Based on Corpus Size

**What:**
Tune Qdrant HNSW parameters based on vector count:
- < 10k vectors: ef_construct=100, m=16 (defaults)
- 10k-100k: ef_construct=150, m=24
- > 100k: ef_construct=200, m=32

**Why:**
- **Quality vs Speed**: Larger corpus needs higher ef_construct for good recall
- **Memory**: Higher m increases memory but improves precision
- **Empirical**: Based on Qdrant recommendations and benchmarks

**Alternatives Considered:**
1. **Fixed parameters** - Rejected: Poor quality at scale
2. **Dynamic tuning** - Rejected: Complex, requires reindexing
3. **No tuning** - Rejected: Suboptimal retrieval

### Decision 10: Audit Logging to Append-Only Storage

**What:**
Log sensitive operations (ingestion, queries, admin actions) to append-only PostgreSQL table or file.

**Why:**
- **Compliance**: Regulatory requirement for data lineage systems
- **Security**: Detect unauthorized access or data exfiltration
- **Debugging**: Trace query patterns and failures

**Alternatives Considered:**
1. **Application logs only** - Rejected: Can be modified/deleted
2. **Third-party service (DataDog, Splunk)** - Rejected: High cost
3. **Blockchain** - Rejected: Overkill, slow

**Implementation:**
- Storage: PostgreSQL with append-only constraint (no UPDATE/DELETE grants)
- Partitioning: Monthly partitions for performance
- Retention: 90 days active, archive to S3 after
- PII redaction: Regex-based (emails, SSNs, credit cards)

## Risks / Trade-offs

### Risk 1: Free Tier Rate Limiting
**Risk:** Groq/OpenRouter free tier has rate limits (30 req/min) that could be exceeded on traffic spikes

**Mitigation:**
- Monitor fallback rate (target < 10%)
- Implement circuit breaker with explicit behavior (see below)
- Queue requests with exponential backoff when rate limited
- Fall back to secondary provider (OpenRouter) if Groq is rate limited
- All providers are free tier (zero API costs)

**Circuit Breaker Behavior:**
When a provider returns rate limit errors (HTTP 429), the circuit breaker opens for that provider. During the open state (60-second cooldown), all requests immediately fail-fast without attempting the provider. After the cooldown period, the circuit enters half-open state, allowing 1 test request. If successful, the circuit closes and normal operation resumes. If the test request fails, the circuit reopens for another 60 seconds. This prevents cascading failures and reduces wasted API calls. Users see a clear error message: "Rate limit exceeded, trying alternate provider" with estimated wait time.

**Frontend Request Cancellation:**
The frontend provides a "Stop Generation" button during active LLM inference. When clicked, the client sends an abort signal to the backend via AbortController (HTTP request cancellation). The backend immediately terminates the LLM streaming connection and cleans up resources. In-progress Ollama/Groq/OpenRouter requests are cancelled via their respective API abort mechanisms. Partial responses are discarded. This prevents wasted compute and improves UX when users realize their query needs refinement.

### Risk 2: Breaking Changes Require Coordinated Deployment
**Risk:** Frontend and backend must be deployed together due to auth changes
**Mitigation:**
- Phased rollout: Deploy backend first with JWT optional (feature flag)
- Migrate frontend to use JWT
- Enforce JWT requirement after frontend migration
- Provide 1-week migration window

### Risk 3: Semantic Cache False Positives
**Risk:** Similar queries (score 0.95) might have different intents
**Mitigation:**
- Start with conservative threshold (0.98)
- Monitor cache hit accuracy via feedback
- Lower threshold gradually if accuracy is good
- Allow cache bypass with `?nocache=true` param

### Risk 4: Audit Log Storage Growth
**Risk:** Audit logs could grow to 10s of GB per month at scale
**Mitigation:**
- Partition by month and archive old partitions
- Store only query hash (not full text) by default
- Compress archived logs (gzip: ~80% reduction)
- Set retention policy (90 days active, 2 years archived)

### Risk 5: HNSW Reindexing Downtime
**Risk:** Changing HNSW params requires full reindex (30+ minutes for large corpus)
**Mitigation:**
- Schedule reindexing during low-traffic windows
- Use blue-green deployment (new collection, swap after index complete)
- Fallback to old collection if new index fails validation

## Migration Plan

### Step 1: Pre-Deployment (Week 0)
1. Run embedding benchmarks to validate model selection
2. Test fallback inference on staging (deliberately OOM Ollama)
3. Create production environment config templates
4. Set up SigNoz or Grafana for metrics
5. Generate JWT secret and API keys

### Step 2: Security-First Deployment (Week 1)
1. Deploy auth middleware with JWT_REQUIRED=false (soft launch)
2. Update frontend to obtain and send JWT tokens
3. Validate frontend auth works on staging
4. Enable JWT_REQUIRED=true in production
5. Monitor for auth errors

### Step 3: Reliability Deployment (Week 2)
1. Deploy inference router with fallback disabled (local-only)
2. Monitor Ollama health and OOM rate
3. Configure Groq API key
4. Enable fallback with circuit breaker (fallback_rate < 10%)
5. Test large queries (> 3000 tokens)

### Step 4: Optimization Deployment (Week 3)
1. Deploy semantic query caching
2. Deploy batch embedding support
3. Deploy prompt templates and token budgets
4. Monitor cache hit rates and latency
5. Tune HNSW parameters based on corpus size

### Step 5: Observability Deployment (Week 4)
1. Deploy custom OpenTelemetry metrics
2. Create SigNoz dashboards
3. Configure alerts (OOM errors, SLO violations, cache hit rate)
4. Validate metrics are being emitted
5. Set up on-call rotation

### Rollback Plan
- **Auth failure:** Set JWT_REQUIRED=false
- **Fallback cost spike:** Disable fallback, accept OOM risk temporarily
- **Performance regression:** Rollback to previous docker image
- **Data corruption:** Restore from snapshot (DuckDB snapshots every 5 min)

## Open Questions

1. **Groq vs OpenRouter for LLM fallback?**
   - Groq: Faster (0.5s vs 2s), free tier 30 req/min, better for bursts
   - OpenRouter: More free models, better reliability SLA
   - Both are 100% free (no API costs)
   - **Decision:** Start with Groq (llama-3.1-70b-versatile), add OpenRouter as secondary fallback

2. **Should we cache negative results (no answer found)?**
   - Pro: Reduces wasted compute on unsolvable queries
   - Con: Prevents improvement if new data is indexed
   - **Decision:** Yes, but with shorter TTL (10 minutes vs 1 hour)

3. **How to handle frontend graph rendering for 10k+ nodes?**
   - Option A: Server-side graph layout + viewport-based streaming
   - Option B: Client-side virtual graph (only render visible nodes)
   - Option C: Limit graph depth/breadth (max 1000 nodes)
   - **Decision:** Start with Option C (simplest), migrate to A if needed

4. **Should audit logs include full query text?**
   - Security team: Yes (detect data exfiltration)
   - Privacy team: No (potential PII exposure)
   - **Decision:** Store query hash by default, full text only if AUDIT_LOG_FULL_QUERIES=true

5. **How to handle model version updates (e.g., llama3.2)?**
   - Option A: Full reindex with new model
   - Option B: Dual indexing (both models for transition period)
   - Option C: Document-level versioning (reindex incrementally)
   - **Decision:** Option A for now (simple), revisit if reindexing time becomes issue

6. **Should embedding benchmarking be mandatory or optional?**
   - Mandatory: Always run on first ingestion, ensures optimal model selection
   - Optional: Run only if BENCHMARK_EMBEDDINGS=true, faster initial setup
   - **Decision:** Optional (default: false), default to nomic-embed-text if not run. Users can benchmark later if they want to optimize further.

7. **Should frontend model selector be persistent per user or per session?**
   - Per user: Store preference in backend DB, consistent across sessions
   - Per session: Store in frontend localStorage, simpler implementation
   - **Decision:** Per session for v1 (localStorage), migrate to user preferences in v2 if requested

## Success Criteria

### Week 2 (Post Phase 1 Deployment)
- ✅ Zero exposed credentials in config files
- ✅ All API endpoints require authentication
- ✅ Zero OOM crashes (fallback working)
- ✅ Audit logs capturing all ingestion and queries

### Week 4 (Post Phase 2 Deployment)
- ✅ Cache hit rate > 40%
- ✅ p95 latency < 2000ms
- ✅ Fallback rate < 10%
- ✅ Embedding benchmarks documented

### Week 6 (Post Phase 3 Deployment)
- ✅ Frontend graph visualization working
- ✅ SLO dashboard showing compliance
- ✅ Alerting validated (manually trigger OOM, check alert)
- ✅ Documentation complete and reviewed

### 3 Months Post-Deployment
- ✅ 99.5% availability achieved
- ✅ Fallback inference cost < $500/month
- ✅ No security incidents
- ✅ User feedback: "Fast and reliable"
