# llm-service Specification

## Purpose
TBD - created by archiving change dockerize-backend-with-huggingface. Update Purpose after archive.
## Requirements
### Requirement: Ollama Integration
The system SHALL use local Ollama installation for LLM operations and embeddings, with health monitoring and fallback support.

#### Scenario: Ollama connectivity check
- **WHEN** system starts
- **THEN** it connects to Ollama at host.docker.internal:11434
- **AND** it validates Ollama is accessible from Docker container
- **AND** it checks available memory and model status
- **AND** it fails fast with clear error if Ollama is not running

#### Scenario: LLM completion request
- **WHEN** system needs LLM completion
- **THEN** it checks Ollama health before request
- **AND** it calls Ollama API on host machine if healthy
- **AND** it uses llama3.1:8b model (or quantized variant if configured)
- **AND** it receives completion within timeout
- **AND** it falls back to remote provider on OOM or timeout

#### Scenario: Required models validation
- **WHEN** system starts
- **THEN** it checks llama3.1:8b model is available (or quantized variant)
- **AND** it checks nomic-embed-text model is available
- **AND** it provides clear error message if models are missing
- **AND** error message includes `ollama pull` commands
- **AND** it validates quantized models if OLLAMA_USE_QUANTIZED=true

#### Scenario: Health monitoring endpoint
- **WHEN** /health/ollama endpoint is called
- **THEN** it returns status (healthy, degraded, unavailable)
- **AND** it includes memory_available_mb estimate
- **AND** it includes models_loaded list
- **AND** it includes fallback_configured boolean
- **AND** it updates every 30 seconds

### Requirement: Embedding Generation
The system SHALL generate vector embeddings using Ollama nomic-embed-text model with caching support.

#### Scenario: Text embedding
- **WHEN** system needs to embed text
- **THEN** it checks Redis cache first using content hash
- **AND** returns cached embedding if available
- **AND** calls Ollama embedding API only on cache miss
- **AND** it uses nomic-embed-text model
- **AND** it returns 768-dimensional vector
- **AND** embedding is deterministic for same input

#### Scenario: Batch embedding
- **WHEN** system needs to embed multiple texts
- **THEN** it checks cache for each text individually
- **AND** only uncached texts are sent to Ollama
- **AND** it returns embeddings in same order as inputs

#### Scenario: Embedding caching
- **WHEN** system embeds previously seen text
- **THEN** it checks Redis cache first
- **AND** it returns cached embedding if available
- **AND** it only calls Ollama for cache misses
- **AND** cache is persisted in Redis with 24-hour TTL
- **AND** cache key uses MD5 hash of content

### Requirement: LlamaIndex Framework Integration
The system SHALL use LlamaIndex framework for unified LLM operations and RAG pipeline.

#### Scenario: LlamaIndex initialization
- **WHEN** system starts
- **THEN** it initializes LlamaIndex with Ollama LLM
- **AND** it configures Ollama embeddings
- **AND** it connects to Qdrant vector store
- **AND** initialization completes within 30 seconds

#### Scenario: Document indexing with LlamaIndex
- **WHEN** SQL file is ingested
- **THEN** it chunks file using semantic chunker
- **AND** it converts chunks to LlamaIndex Document objects
- **AND** it generates embeddings via Ollama
- **AND** it stores in Qdrant via LlamaIndex VectorStoreIndex
- **AND** metadata is preserved (file_path, chunk_type, tables, columns)

#### Scenario: RAG query execution
- **WHEN** user asks lineage question
- **THEN** LlamaIndex retrieves top 5 relevant chunks from Qdrant
- **AND** it constructs prompt with retrieved context
- **AND** it calls Ollama LLM with augmented prompt
- **AND** it returns response with source citations

### Requirement: RAG Pipeline Components
The system SHALL implement complete RAG pipeline using LlamaIndex abstractions with adaptive response synthesis.

#### Scenario: Vector store integration
- **WHEN** LlamaIndex needs vector storage
- **THEN** it uses QdrantVectorStore with code_chunks collection
- **AND** it stores 768-dimensional vectors
- **AND** it preserves document metadata
- **AND** it supports metadata filtering
- **AND** HNSW parameters are configured per environment

#### Scenario: Query engine creation
- **WHEN** system creates query engine
- **THEN** it uses VectorStoreIndex.as_query_engine()
- **AND** it configures similarity_top_k based on query type (5 for semantic, 10 for deep)
- **AND** it sets response_mode to "compact" for top_k <= 10, "tree_summarize" for top_k > 10
- **AND** query engine is reusable across requests

#### Scenario: Response synthesis with adaptive mode
- **WHEN** query engine generates response with top_k > 10
- **THEN** it uses tree_summarize mode to handle large context
- **AND** it hierarchically summarizes chunks to fit context window
- **AND** it preserves source citations through summarization layers
- **AND** final response includes all source file references

### Requirement: Error Handling and Resilience
The system SHALL handle Ollama connection failures gracefully.

#### Scenario: Ollama unavailable on startup
- **WHEN** Ollama is not running on host
- **THEN** system logs clear error message
- **AND** error includes troubleshooting steps
- **AND** health check endpoint shows degraded status
- **AND** system does not crash

#### Scenario: Ollama timeout during query
- **WHEN** Ollama request times out
- **THEN** system retries up to 3 times
- **AND** it uses exponential backoff (2s, 4s, 8s)
- **AND** it logs timeout details
- **AND** it returns error to user after retries exhausted

#### Scenario: Service degradation
- **WHEN** Ollama becomes unavailable during runtime
- **THEN** health check endpoint shows degraded status
- **AND** cached results are used when available
- **AND** new requests return informative error
- **AND** system auto-recovers when Ollama is accessible

### Requirement: Redis Caching Integration
The system SHALL use Redis for caching embeddings and query results.

#### Scenario: Embedding cache
- **WHEN** embedding is generated
- **THEN** it is stored in Redis with content hash as key
- **AND** cache TTL is set to 24 hours
- **AND** cache hit rate is tracked
- **AND** cache misses trigger Ollama API calls

#### Scenario: Query result caching
- **WHEN** RAG query completes
- **THEN** result is cached in Redis with query hash as key
- **AND** cache TTL is set to 1 hour
- **AND** identical queries return cached results
- **AND** cache can be invalidated on new document ingestion

#### Scenario: Cache metrics
- **WHEN** system is running
- **THEN** it tracks cache hit/miss rates
- **AND** metrics are exposed via /api/v1/rag/status endpoint
- **AND** metrics show Ollama API call savings

### Requirement: LlamaIndex Observability
The system SHALL log LlamaIndex operations for debugging and monitoring.

#### Scenario: Query logging
- **WHEN** RAG query is executed
- **THEN** system logs query text
- **AND** it logs retrieved chunks (count and sources)
- **AND** it logs LLM prompt and response
- **AND** it logs total latency breakdown (retrieval, generation)

#### Scenario: Performance metrics
- **WHEN** system processes requests
- **THEN** it tracks embedding latency
- **AND** it tracks retrieval latency
- **AND** it tracks generation latency
- **AND** it tracks end-to-end query latency

### Requirement: Feature Flag for RAG Implementations
The system SHALL support switching between old and new RAG implementations during transition.

#### Scenario: Feature flag enabled
- **WHEN** USE_LLAMAINDEX=true in environment
- **THEN** system uses LlamaIndex RAG pipeline
- **AND** old RAG code is not executed
- **AND** /health endpoint indicates LlamaIndex mode

#### Scenario: Feature flag disabled
- **WHEN** USE_LLAMAINDEX=false in environment
- **THEN** system uses existing RAG implementation
- **AND** LlamaIndex is not initialized
- **AND** /health endpoint indicates legacy mode

#### Scenario: Gradual rollout
- **WHEN** testing new implementation
- **THEN** both implementations can be tested side-by-side
- **AND** results can be compared for validation
- **AND** rollback is instant by changing env var

### Requirement: Metadata Filtering
The system SHALL support filtering by metadata during vector search.

#### Scenario: Filter by file path
- **WHEN** query specifies source file
- **THEN** vector search filters to chunks from that file only
- **AND** retrieval is limited to matching metadata
- **AND** response indicates filtered results

#### Scenario: Filter by entity type
- **WHEN** query asks about specific entity type (table, view, etc.)
- **THEN** vector search filters by chunk_type metadata
- **AND** only relevant entity types are retrieved
- **AND** improves answer relevance

### Requirement: OpenRouterService for Zero-Cost Inference
The system SHALL provide a dedicated service for routing lineage inference requests to free-tier OpenRouter models with strict cost controls.

#### Scenario: OpenRouterService initialization
- **WHEN** system initializes `OpenRouterService`
- **THEN** it requires `OPENROUTER_API_KEY` from environment
- **AND** initializes httpx async client for HTTP calls
- **AND** loads `FREE_TIER_MODELS` whitelist
- **AND** sets default model to `google/gemini-2.0-flash-exp:free`

#### Scenario: Predict lineage method
- **WHEN** `predict_lineage(code_snippet, context_nodes)` is called
- **THEN** service constructs a structured prompt with code and context
- **AND** makes POST request to OpenRouter `/api/v1/chat/completions`
- **AND** uses `response_format={"type": "json_object"}` for strict JSON mode
- **AND** parses response into list of `LineageEdgeProposal` objects
- **AND** validates proposals before returning

#### Scenario: JSON-only response mode
- **WHEN** OpenRouter is called with strict JSON mode
- **THEN** request header includes `"response_format": {"type": "json_object"}`
- **AND** system prompt explicitly requires JSON-only output
- **AND** any non-JSON response is caught and logged as error
- **AND** empty list is returned on parsing failure (fail-open)

#### Scenario: Routing guard enforcement
- **WHEN** user specifies a model for lineage inference
- **THEN** `OpenRouterService` validates model against `FREE_TIER_MODELS`
- **AND** if model is not in whitelist, downgrades to default free model
- **AND** logs warning with original model and downgrade reason
- **AND** proceeds with free-tier model

#### Scenario: Rate limit handling
- **WHEN** OpenRouter returns 429 (Rate Limit Exceeded)
- **THEN** service catches the error and logs it
- **AND** returns empty list (fail-open, no crash)
- **AND** circuit breaker may open to prevent further requests
- **AND** system continues using deterministic lineage only

#### Scenario: Service unavailable handling
- **WHEN** OpenRouter returns 503 (Service Unavailable)
- **THEN** service catches the error and logs it
- **AND** returns empty list (fail-open)
- **AND** deterministic lineage parsing continues unaffected

#### Scenario: Lineage proposal structure
- **WHEN** OpenRouter returns proposals
- **THEN** each proposal conforms to `LineageEdgeProposal` schema:
  ```python
  {
    "source_node": "str",           # Source entity identifier
    "target_node": "str",           # Target entity identifier
    "relationship_type": "READS|WRITES",  # Relationship type
    "confidence": 0.85,             # Float 0.0-1.0
    "reasoning": "str"              # Brief explanation
  }
  ```

### Requirement: Knowledge Graph Enrichment Agent
The system SHALL provide a KG agent that proposes new edges using free-tier OpenRouter Devstral and writes them directly to Neo4j.

#### Scenario: KG agent model selection
- **WHEN** KG enrichment runs
- **THEN** it uses `mistralai/devstral-2512:free` as the default model
- **AND** requests are validated against `FREE_TIER_MODELS`

#### Scenario: KG agent edge write
- **WHEN** KG agent proposes edges
- **THEN** it writes edges directly to Neo4j
- **AND** each edge includes metadata: `source="llm"`, `model`, `confidence`, `status`
- **AND** writes are associated with the current ingestion context (project_id, file_path)

#### Scenario: KG agent logging
- **WHEN** KG agent completes
- **THEN** ingestion logs include:
  - proposed edge count
  - accepted edge count
  - model name
  - confidence summary

### Requirement: Free-Tier Model Enforcement
The system SHALL enforce zero-cost inference by restricting cloud LLM requests to free-tier models only.

#### Scenario: Free-tier model requested
- **WHEN** user or system requests generation with a free-tier model (e.g., `google/gemini-2.0-flash-exp:free`)
- **THEN** the request proceeds without modification
- **AND** the specified model is used for inference

#### Scenario: Non-free model requested
- **WHEN** a non-free model is requested (e.g., `gpt-4`, `claude-3-opus`)
- **THEN** the system SHALL automatically downgrade to `google/gemini-2.0-flash-exp:free`
- **AND** it logs a warning with the original model name and downgrade reason
- **AND** the response completes successfully with the fallback model

#### Scenario: Free-tier model whitelist
- **WHEN** system initializes
- **THEN** it SHALL define a whitelist of approved free-tier models
- **AND** whitelist includes at minimum:
  - `google/gemini-2.0-flash-exp:free` (1M context, fast general-purpose)
  - `mistralai/mistral-7b-instruct:free` (32K context, balanced chat)
  - `mistralai/devstral-2512:free` (128K context, code/structure specialist)
  - `meta-llama/llama-3.1-8b-instruct:free` (128K context, general-purpose)
  - `deepseek/deepseek-r1-0528:free` (64K context, reasoning/CoT)
  - `qwen/qwen3-4b:free` (32K context, fast efficient)

### Requirement: LLM Routing and Fallback
The system SHALL route LLM requests to local Ollama by default, with automatic fallback to free-tier cloud providers when needed.

#### Scenario: Free-tier model enforcement
- **WHEN** user or system requests a specific cloud model
- **THEN** the router validates model against `FREE_TIER_MODELS` whitelist
- **AND** if model is not free-tier, it downgrades to `google/gemini-2.0-flash-exp:free`
- **AND** it logs a warning with original and replacement model names
- **AND** it returns completion using the free-tier model

#### Scenario: Cost tracking
- **WHEN** a non-free model is requested
- **THEN** system logs the event with request metadata
- **AND** metrics counter is incremented for monitoring
- **AND** user receives response with header indicating model downgrade

#### Scenario: Ollama connectivity check
- **WHEN** system starts
- **THEN** it connects to Ollama at host.docker.internal:11434
- **AND** it validates Ollama is accessible from Docker container
- **AND** it fails fast with clear error if Ollama is not running

#### Scenario: LLM completion request
- **WHEN** system needs LLM completion
- **THEN** it calls Ollama API on host machine
- **AND** it uses llama3.1:8b model
- **AND** it receives completion within 10 seconds
- **AND** it handles connection errors gracefully

### Requirement: Document indexing with LlamaIndex
The system SHALL index code chunks using LlamaIndex for all ingestion entry points.

#### Scenario: Index files from all ingestion sources
- **WHEN** a file is ingested via `/api/v1/ingest`, `/api/v1/files/upload`, or `/api/v1/github/ingest`
- **THEN** the system chunks the file using the semantic chunker (sql, python, or generic)
- **AND** it converts chunks to LlamaIndex Document objects
- **AND** it generates embeddings via Ollama
- **AND** it stores embeddings in Qdrant via VectorStoreIndex
- **AND** metadata is preserved (file_path, relative_path, chunk_type, tables, columns, source, project_id, repository_id)

### Requirement: Chat endpoints SHALL NOT use LlamaIndex for generation
The system SHALL use direct retrieval (Qdrant + Neo4j) with OpenRouter free-tier models for all `/api/chat/*` endpoints, without LlamaIndex abstractions.

#### Scenario: Chat endpoint routing without LlamaIndex
- **WHEN** any `/api/chat/*` endpoint receives a request
- **THEN** it retrieves context directly from Qdrant vector store and/or Neo4j graph store
- **AND** it constructs prompts manually using endpoint-specific system prompts
- **AND** it calls OpenRouter free-tier models for generation (never LlamaIndex query engine)
- **AND** it parses LLM output into structured internal format (`answer`, `evidence`, `next_actions`, `warnings`)
- **AND** it transforms internal format to `ChatResponse` API schema for return
- **AND** it populates the `model` field at root level with the actual model used (e.g., `"deepseek/deepseek-r1-0528:free"`)
- **AND** if fallback occurred, the `model` field reflects the successful fallback model, not the original failed model

#### Scenario: Embeddings still use Ollama
- **WHEN** chat endpoints need to embed user queries
- **THEN** they use local Ollama for embedding generation
- **AND** embeddings are used for Qdrant vector similarity search
- **AND** OpenRouter is only used for text generation, not embeddings

### Requirement: Base system prompt for all chat endpoints
The system SHALL use a shared base system prompt that enforces evidence-based responses and structured JSON output.

#### Scenario: Base prompt applied to all endpoints
- **WHEN** any `/api/chat/*` endpoint constructs an LLM request
- **THEN** it includes the base system prompt:
  ```
  You are the Financial Lineage Tool assistant. Your job is to answer questions about data lineage, dependencies, transformations, and repository artifacts using ONLY the evidence provided in the request context (vector snippets, graph results, and metadata). Do not invent tables, columns, files, edges, or SQL logic.

  Rules:
  - Treat Neo4j/graph evidence as authoritative for lineage claims (upstream/downstream, DERIVES/READS_FROM, dependency edges).
  - Treat vector snippets as supporting evidence (code or docs excerpts). If evidence is missing or ambiguous, say so and propose what to search next.
  - Prefer precise, testable statements (file path, object name, query/view name, edge/path, confidence if provided).
  - Never mention internal implementation details (no "I used Qdrant/Neo4j" unless asked). Just cite evidence identifiers passed in.
  - Never output hidden reasoning. Provide final conclusions only.

  Output format:
  Return a single JSON object with:
  {
    "answer": string,                  // concise, directly addresses the user
    "evidence": [                      // 0..N items
      { "type": "graph|chunk|doc", "id": string, "note": string }
    ],
    "next_actions": [string],          // 0..N suggested follow-ups (queries to run, entities to inspect)
    "warnings": [string]               // 0..N (missing evidence, conflicts, assumptions)
  }

  If the user asks for code changes, respond with steps and minimal patches, grounded in evidence.
  ```
- **AND** endpoint-specific additions are appended to this base prompt

#### Scenario: JSON-only output enforcement with safe fallback
- **WHEN** LLM response is received (except streaming endpoints)
- **THEN** the system attempts to parse it as JSON
- **AND** validates it has `answer`, `evidence`, `next_actions`, and `warnings` keys
- **AND** if parsing fails or keys are missing, logs full response with model name and endpoint
- **AND** returns safe fallback response with warnings array indicating malformed LLM output
- **AND** increments `chat_malformed_response_count` metric for monitoring

### Requirement: /api/chat/deep endpoint-specific prompt
The system SHALL append deep-analysis-specific instructions to the base prompt for `/api/chat/deep` requests.

#### Scenario: Deep endpoint prompt additions
- **WHEN** `/api/chat/deep` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for DEEP:
  - Synthesize across graph evidence + multiple snippets. If they conflict, call it out and pick the most authoritative source.
  - When explaining lineage, include: (a) the key path(s), (b) the transformation boundary (view/job/model), and (c) what to verify next.
  - Keep the answer structured in paragraphs or bullets inside the "answer" string, but still emit valid JSON.
  ```
- **AND** uses primary model `deepseek/deepseek-r1-0528:free` with fallbacks to `google/gemini-2.0-flash-exp:free`, then `meta-llama/llama-3.1-8b-instruct:free`

#### Scenario: Deep endpoint retrieves top 10 context
- **WHEN** `/api/chat/deep` retrieves context
- **THEN** it fetches top 10 relevant chunks from Qdrant
- **AND** it fetches related graph nodes and edges from Neo4j when applicable
- **AND** it includes both in the LLM prompt as structured evidence

### Requirement: /api/chat/graph endpoint-specific prompt
The system SHALL append graph-first instructions to the base prompt for `/api/chat/graph` requests.

#### Scenario: Graph endpoint prompt additions
- **WHEN** `/api/chat/graph` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for GRAPH:
  - Answer using graph evidence first. If no graph evidence supports a lineage claim, do not claim it.
  - Summarize nodes, edges, and paths clearly (entity names + relationship type). Avoid long prose.
  ```
- **AND** uses primary model `mistralai/devstral-2512:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `google/gemini-2.0-flash-exp:free`

#### Scenario: Graph endpoint prioritizes Neo4j evidence
- **WHEN** `/api/chat/graph` retrieves context
- **THEN** it queries Neo4j first for nodes, edges, and paths
- **AND** it includes vector chunks only as supplementary evidence
- **AND** the prompt explicitly marks graph evidence as authoritative

### Requirement: /api/chat/semantic endpoint-specific prompt
The system SHALL append fast-search instructions to the base prompt for `/api/chat/semantic` requests.

#### Scenario: Semantic endpoint prompt additions
- **WHEN** `/api/chat/semantic` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for SEMANTIC:
  - Focus on the most relevant snippets and return a short summary.
  - If the user asks lineage questions and no graph evidence is present, explicitly recommend calling /api/chat/deep or /api/chat/graph in next_actions.
  - Keep "answer" under ~1200 characters unless the user explicitly asked for detail.
  ```
- **AND** uses primary model `google/gemini-2.0-flash-exp:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `mistralai/mistral-7b-instruct:free`

#### Scenario: Semantic endpoint retrieves top 5 context
- **WHEN** `/api/chat/semantic` retrieves context
- **THEN** it fetches top 5 relevant chunks from Qdrant
- **AND** it skips Neo4j queries for speed
- **AND** the response is optimized for low latency

### Requirement: /api/chat/text endpoint-specific prompt
The system SHALL append no-RAG instructions to the base prompt for `/api/chat/text` requests.

#### Scenario: Text endpoint prompt additions
- **WHEN** `/api/chat/text` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for TEXT:
  - You have no retrieval context. Do not pretend you saw the repo or graph.
  - Provide general guidance, and put specific "what I would need" items into next_actions.
  ```
- **AND** uses primary model `google/gemini-2.0-flash-exp:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `mistralai/mistral-7b-instruct:free`

#### Scenario: Text endpoint skips retrieval
- **WHEN** `/api/chat/text` processes a request
- **THEN** it does NOT query Qdrant or Neo4j
- **AND** it passes only user query and base prompt to LLM
- **AND** it returns general guidance without specific evidence

### Requirement: /api/chat/title endpoint-specific prompt
The system SHALL append title-generation instructions to the base prompt for `/api/chat/title` requests.

#### Scenario: Title endpoint prompt additions
- **WHEN** `/api/chat/title` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for TITLE:
  - Produce a short title (3–7 words) that describes the user's main intent. Output JSON with:
  { "answer": "<title>", "evidence": [], "next_actions": [], "warnings": [] }
  ```
- **AND** uses primary model `google/gemini-2.0-flash-exp:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `mistralai/mistral-7b-instruct:free`

#### Scenario: Title endpoint returns compact response
- **WHEN** `/api/chat/title` processes a request
- **THEN** it returns JSON with `answer` containing 3-7 word title
- **AND** `evidence`, `next_actions`, and `warnings` are empty arrays
- **AND** response is returned within 2 seconds

### Requirement: Model fallback routing for chat endpoints
The system SHALL define primary/secondary/tertiary free-tier models for each chat endpoint and retry through fallbacks on errors.

#### Scenario: Primary model success
- **WHEN** chat endpoint calls primary model and it succeeds
- **THEN** the response is returned immediately
- **AND** no fallback models are tried
- **AND** the `model` field in response contains the primary model identifier (e.g., `"deepseek/deepseek-r1-0528:free"` for `/api/chat/deep`)

#### Scenario: Primary model fails, fallback to secondary
- **WHEN** primary model returns error, rate limit (429), timeout, or parse failure
- **THEN** the system logs the error with model name, endpoint, and reason
- **AND** it retries with secondary model after exponential backoff (base_delay * backoff_factor^(retry_count-1), e.g., 2.0s for first fallback)
- **AND** it uses the same prompt and context
- **AND** increments `chat_model_fallback_count{endpoint, from_model, to_model, reason}` metric
- **AND** fallback is triggered by FAILURE only, not by slow response within timeout
- **AND** if secondary succeeds, the `model` field in response contains the secondary model identifier (e.g., `"google/gemini-2.0-flash-exp:free"`)
- **AND** the primary model failure is logged server-side but NOT exposed to the client in the response

#### Scenario: Secondary fails, fallback to tertiary
- **WHEN** secondary model also fails
- **THEN** the system logs the error with model name and reason
- **AND** it retries with tertiary model after exponential backoff (2.0s * 2.0^1 = 4.0s for second fallback, well-gapped)
- **AND** if tertiary fails, returns 503 Service Unavailable with JSON body:
  ```json
  {
    "error": "All free-tier models exhausted for this endpoint",
    "endpoint": "/api/chat/deep",
    "attempts": [
      {"model": "deepseek/deepseek-r1-0528:free", "error": "Rate limit exceeded (429)", "timestamp": "2026-01-13T10:30:00Z"},
      {"model": "google/gemini-2.0-flash-exp:free", "error": "Timeout after 90s", "timestamp": "2026-01-13T10:32:00Z"},
      {"model": "meta-llama/llama-3.1-8b-instruct:free", "error": "Service unavailable (503)", "timestamp": "2026-01-13T10:36:00Z"}
    ],
    "retry_after": 120
  }
  ```
- **AND** increments `chat_all_models_failed{endpoint}` metric
- **AND** `retry_after` suggests client back-off (2 minutes for free-tier recovery)

#### Scenario: Model whitelist enforcement during fallback
- **WHEN** any fallback model is selected
- **THEN** the system validates it is in `FREE_TIER_MODELS` whitelist
- **AND** if not whitelisted, it downgrades to `google/gemini-2.0-flash-exp:free`
- **AND** logs warning with original model and downgrade reason

### Requirement: Free-tier model whitelist for chat endpoints
The system SHALL maintain a whitelist of approved zero-cost OpenRouter models and enforce it for all chat generation requests.

#### Scenario: Chat endpoint model whitelist
- **WHEN** system initializes chat routing
- **THEN** it defines `FREE_TIER_MODELS` whitelist containing:
  - `google/gemini-2.0-flash-exp:free` (1M context, fast general-purpose)
  - `mistralai/mistral-7b-instruct:free` (32K context, balanced chat)
  - `mistralai/devstral-2512:free` (128K context, code/structure specialist)
  - `meta-llama/llama-3.1-8b-instruct:free` (128K context, general-purpose)
  - `deepseek/deepseek-r1-0528:free` (64K context, reasoning/CoT)
  - `qwen/qwen3-4b:free` (32K context, fast efficient)
- **AND** only these models are allowed for chat endpoints

#### Scenario: Non-free model requested in chat
- **WHEN** a non-free model is requested (e.g., user override or misconfiguration)
- **THEN** the system downgrades to `google/gemini-2.0-flash-exp:free`
- **AND** logs warning with original model name and "not in FREE_TIER_MODELS" reason
- **AND** proceeds with free-tier model

### Requirement: CQRS-based chat endpoint routing with intent-optimized models
The system SHALL route chat requests using Command Query Responsibility Segregation (CQRS) principles, mapping user intent to retrieval strategy and model selection.

#### Scenario: CQRS routing table
- **WHEN** system initializes chat routing configuration
- **THEN** it defines intent-to-strategy mappings (time budgets are typical targets, not hard limits):
  - `/api/chat/deep`: Complex Reasoning → Hybrid Retrieval (top 10 vector + 2-hop graph) → DeepSeek R1 (reasoning/CoT) → ~30-60s typical (free-tier variable)
  - `/api/chat/graph`: Structure/Lineage Analysis → Graph Traversal (upstream/downstream paths + schema) → Devstral 2 (code/structure aware) → ~10-20s typical
  - `/api/chat/semantic`: Lookup/Search → Vector Search (top 5 chunks) → Gemini 2.0 Flash (high speed/context) → ~5-10s typical
  - `/api/chat/text`: General/Help → No RAG (direct context only) → Llama 3.1 8B (general chat) → ~3-8s typical
  - `/api/chat/title`: Session Naming → No RAG → Gemini 2.0 Flash or Llama 3.1 → ~2-5s typical
- **AND** time budgets reflect free-tier model latency variability (no SLA guarantees)
- **AND** fallbacks are triggered by errors (429, 503, timeout, parse failure), NOT by exceeding time budget

#### Scenario: Default models per endpoint with temperature settings
- **WHEN** system routes chat requests
- **THEN** it uses these default models (primary/secondary/tertiary) with temperature settings:
  - `/api/chat/deep`: `deepseek/deepseek-r1-0528:free` (temp=0.6 for reasoning exploration) → `mistralai/devstral-2512:free` (temp=0.6) → `google/gemini-2.0-flash-exp:free` (temp=0.6)
  - `/api/chat/graph`: `mistralai/devstral-2512:free` (temp=0.1 for strict graph interpretation) → `deepseek/deepseek-r1-0528:free` (temp=0.1) → `google/gemini-2.0-flash-exp:free` (temp=0.1)
  - `/api/chat/semantic`: `google/gemini-2.0-flash-exp:free` (temp=0.2) → `qwen/qwen3-4b:free` (temp=0.2) → `mistralai/mistral-7b-instruct:free` (temp=0.2)
  - `/api/chat/text`: `google/gemini-2.0-flash-exp:free` (temp=0.3) → `mistralai/mistral-7b-instruct:free` (temp=0.3) → `qwen/qwen3-4b:free` (temp=0.3)
  - `/api/chat/title`: `google/gemini-2.0-flash-exp:free` (temp=0.2) → `mistralai/mistral-7b-instruct:free` (temp=0.2) → `qwen/qwen3-4b:free` (temp=0.2)
- **AND** these mappings are exposed via `/api/v1/config` (see api-endpoints spec)
- **AND** temperature is configurable per endpoint via environment variables or config file

#### Scenario: Hybrid retrieval for deep mode
- **WHEN** `/api/chat/deep` builds context
- **THEN** it executes hybrid retrieval:
  1. Embeds query using local Ollama
  2. Fetches top 10 relevant chunks from Qdrant vector search
  3. Extracts entity mentions from query (tables, views, functions via regex/keyword)
  4. Executes 2-hop graph traversal from extracted entities in Neo4j
  5. Serializes both vector snippets and graph paths into structured context string
- **AND** context includes evidence IDs (URNs) for all chunks and graph entities
- **AND** total context construction completes within 5 seconds

#### Scenario: Graph-first retrieval for graph mode
- **WHEN** `/api/chat/graph` builds context
- **THEN** it prioritizes Neo4j:
  1. Extracts entity mentions from query
  2. Queries Neo4j for upstream/downstream paths (up to 3 hops)
  3. Fetches node schema and edge metadata
  4. Optionally includes top 3 relevant chunks as supplementary evidence
  5. Formats graph paths as: `node1 -[RELATIONSHIP]-> node2`
- **AND** context explicitly marks graph evidence as authoritative
- **AND** graph query completes within 3 seconds

#### Scenario: Vector-only retrieval for semantic mode
- **WHEN** `/api/chat/semantic` builds context
- **THEN** it executes fast vector search:
  1. Embeds query using local Ollama
  2. Fetches top 5 relevant chunks from Qdrant
  3. Skips Neo4j queries for speed
  4. Formats chunks with URNs and text excerpts
- **AND** retrieval completes within 1 second
- **AND** if query contains lineage keywords (upstream, downstream, depends), includes warning suggesting `/api/chat/deep` or `/api/chat/graph`

### Requirement: Evidence ID format for resolution
The system SHALL format evidence identifiers using the URN scheme defined in the api-endpoints spec.

#### Scenario: Evidence URN alignment
- **WHEN** system includes evidence identifiers in chat responses
- **THEN** it uses `urn:li:{entity_type}:{project_id}:{asset_path}` as defined in `api-endpoints` requirements
- **AND** it includes `entity_type` and `asset_path` conventions from the API contract

### Requirement: DeepSeek R1 reasoning token handling
The system SHALL enforce strict JSON mode to suppress DeepSeek R1's Chain-of-Thought "thinking" tokens in chat responses.

#### Scenario: DeepSeek R1 JSON-only mode
- **WHEN** `/api/chat/deep` calls `deepseek/deepseek-r1-0528:free`
- **THEN** it includes `response_format={"type": "json_object"}` in the API request
- **AND** this forces DeepSeek to output only valid JSON, suppressing internal reasoning tokens
- **AND** if DeepSeek still emits thinking tokens, the JSON parser will fail and trigger safe fallback

#### Scenario: Reasoning preservation in logs
- **WHEN** DeepSeek R1 generates response in debug mode
- **THEN** raw response (including any leaked reasoning tokens) is logged at DEBUG level
- **AND** only the parsed JSON is returned to client
- **AND** logs are tagged with `model=deepseek-r1, endpoint=deep`

### Requirement: Resilient LLM gateway with retry logic
The system SHALL wrap all OpenRouter calls in a resilient gateway that handles rate limits, timeouts, and model failures.

#### Scenario: Retry configuration
- **WHEN** system initializes LLM gateway
- **THEN** it loads configuration:
  - `max_retries`: 3 (primary + 2 fallbacks)
  - `backoff_factor`: 2.0 (exponential backoff multiplier for well-gapped retries)
  - `base_delay`: 2.0 seconds (initial retry delay, gives free-tier models time to recover)
  - `timeout_per_request`: 90 seconds for deep (DeepSeek R1 can be slow), 45 seconds for graph/semantic, 30 seconds for text/title
- **AND** configuration is stored in environment variables and loaded via `config.py`
- **AND** timeouts are generous to accommodate free-tier variability

#### Scenario: Rate limit (429) handling
- **WHEN** OpenRouter returns 429 (Rate Limit Exceeded)
- **THEN** system parses `Retry-After` header if present
- **AND** waits for `max(Retry-After, base_delay * backoff_factor^(retry-1))` seconds before fallback
- **AND** falls back to next model (does NOT retry same model on rate limit)
- **AND** logs rate limit with model, endpoint, retry_after value, and timestamp
- **AND** well-gapped fallback (minimum 2s, up to 4s for second fallback) gives free-tier time to recover

#### Scenario: Timeout handling
- **WHEN** OpenRouter request exceeds timeout_per_request (90s for deep, 45s for graph/semantic, 30s for text/title)
- **THEN** system cancels request and logs timeout with model, endpoint, and timeout value
- **AND** waits for backoff delay (2s for first fallback, 4s for second) before next model
- **AND** increments `chat_timeout_count{endpoint, model}` metric
- **AND** does NOT immediately retry (gives downstream systems time to recover)

#### Scenario: Service unavailable (503) handling
- **WHEN** OpenRouter returns 503 (Service Unavailable)
- **THEN** system logs error and immediately falls back to next model
- **AND** does NOT retry the same model (assume temporary outage)
- **AND** increments `chat_service_unavailable_count{endpoint, model}` metric

### Requirement: Context window management for chat endpoints
The system SHALL construct context strings that fit within model token limits while preserving evidence fidelity.

#### Scenario: Context truncation for deep mode
- **WHEN** `/api/chat/deep` builds context exceeding 8000 tokens (estimated)
- **THEN** it prioritizes graph evidence over vector chunks
- **AND** truncates vector chunks from oldest to newest
- **AND** includes warning in response: `"warnings": ["Context truncated: X chunks omitted due to token limit"]`
- **AND** logs truncation event with original and final chunk counts

#### Scenario: Context serialization format
- **WHEN** system serializes Qdrant chunks and Neo4j paths into context string
- **THEN** it uses structured format:
  ```
  ## Vector Evidence
  [urn:li:qdrant-chunk:project_id:code_chunks/abc123]
  File: src/models/transaction.py
  Type: python_class
  Content: class Transaction(BaseModel): ...

  [urn:li:qdrant-chunk:project_id:code_chunks/def456]
  File: sql/views/customer_summary.sql
  Type: sql_view
  Content: CREATE VIEW customer_summary AS SELECT ...

  ## Graph Evidence
  [urn:li:neo4j-node:project_id:Table/transactions] -[READS_FROM]-> [urn:li:neo4j-node:project_id:Table/customers]
  Path: transactions (Table) -> READS_FROM -> customers (Table)
  Confidence: 0.95
  Source: deterministic

  ## User Query
  {user_query}
  ```
- **AND** evidence IDs are preserved for LLM to include in `evidence` array

### Requirement: Parallel Query Execution
The system SHALL execute independent query operations concurrently to reduce response latency.

#### Scenario: Parallel embedding and graph search
- **WHEN** user submits a chat query
- **THEN** system executes embedding generation and graph search in parallel
- **AND** both operations complete before context building
- **AND** total latency is max(embedding_time, graph_time) not sum

#### Scenario: Error handling in parallel execution
- **WHEN** one parallel operation fails
- **THEN** system continues with successful operations
- **AND** logs the failure for debugging
- **AND** returns partial results to user

### Requirement: Embedding Cache
The system SHALL cache embeddings in Redis to avoid redundant Ollama calls.

#### Scenario: Cache hit for repeated query
- **WHEN** user submits a previously seen query
- **THEN** system retrieves embedding from Redis cache
- **AND** Ollama API is not called
- **AND** response time is reduced by ~200ms

#### Scenario: Cache miss for new query
- **WHEN** user submits a new query
- **THEN** system generates embedding via Ollama
- **AND** stores embedding in Redis with 24-hour TTL
- **AND** uses content MD5 hash as cache key

#### Scenario: Cache unavailable
- **WHEN** Redis is not connected
- **THEN** system falls back to direct Ollama calls
- **AND** logs warning about disabled caching
- **AND** functionality is not degraded

### Requirement: Batch Graph Queries
The system SHALL batch multiple entity lookups into single Neo4j query.

#### Scenario: Multi-word entity search
- **WHEN** query contains multiple potential entity names
- **THEN** system executes single Cypher query with IN clause
- **AND** returns all matching entities in one round-trip
- **AND** latency is constant regardless of word count

#### Scenario: Case-insensitive matching
- **WHEN** entity names have different casing
- **THEN** batch query matches both original and lowercase
- **AND** all relevant entities are found

### Requirement: Optional Memory Context
The system SHALL support skipping memory retrieval for performance.

#### Scenario: Skip memory flag enabled
- **WHEN** request includes skip_memory=true
- **THEN** system bypasses memory context retrieval
- **AND** saves ~300ms latency
- **AND** query proceeds with empty memory context

#### Scenario: First message in session
- **WHEN** session has no prior history
- **THEN** memory retrieval returns empty context quickly
- **AND** no unnecessary vector search is performed

### Requirement: Streaming Chat Responses
The system SHALL support Server-Sent Events (SSE) for real-time response streaming.

#### Scenario: Streaming endpoint request
- **WHEN** client calls POST /api/chat/deep/stream
- **THEN** system returns Content-Type: text/event-stream
- **AND** sends response tokens as they are generated
- **AND** client sees response incrementally

#### Scenario: Stream completion
- **WHEN** LLM completes generation
- **THEN** system sends final event with sources and metadata
- **AND** closes SSE connection
- **AND** total response matches non-streaming endpoint

#### Scenario: Stream error handling
- **WHEN** error occurs during streaming
- **THEN** system sends error event to client
- **AND** closes connection gracefully
- **AND** logs error details

### Requirement: Hybrid Inference Strategy with Automatic Fallback
The system SHALL route inference requests to local Ollama by default, with automatic fallback to remote providers (Groq, OpenRouter) when Ollama is unavailable or memory-constrained.

#### Scenario: Ollama health check before inference
- **WHEN** system receives an inference request
- **THEN** it checks Ollama health status (memory available, model loaded)
- **AND** it estimates query token count
- **AND** if health is good and tokens < 3000, route to Ollama
- **AND** if health is degraded or tokens >= 3000, route to fallback provider

#### Scenario: Automatic fallback on OOM
- **WHEN** Ollama returns OOM error during generation
- **THEN** system catches the error
- **AND** it logs fallback event with metadata (query size, error type)
- **AND** it retries the request on configured fallback provider (Groq/OpenRouter)
- **AND** response includes source provider in metadata

#### Scenario: Cost-optimized routing
- **WHEN** both Ollama and fallback are available
- **THEN** system prefers Ollama for queries < 3000 tokens (free)
- **AND** it uses fallback only for large contexts or Ollama failures
- **AND** it tracks cost metrics (tokens sent to paid providers)
- **AND** it logs routing decisions for analysis

#### Scenario: Fallback provider configuration
- **WHEN** system starts
- **THEN** it reads INFERENCE_FALLBACK_PROVIDER environment variable (groq|openrouter)
- **AND** it reads corresponding API key (GROQ_API_KEY or OPENROUTER_API_KEY)
- **AND** if fallback is not configured, system logs warning but continues
- **AND** health endpoint shows fallback status

### Requirement: Ollama Memory Monitoring and Adaptive Context Management
The system SHALL monitor Ollama memory usage and dynamically adjust context window to prevent OOM crashes.

#### Scenario: Query size estimation before generation
- **WHEN** RAG query is prepared
- **THEN** system estimates total tokens (context + query + response buffer)
- **AND** if estimated tokens > OLLAMA_CONTEXT_WINDOW * 0.8, trigger trimming
- **AND** context is reduced by dropping lowest-relevance chunks
- **AND** system logs context trimming event

#### Scenario: Quantized model support
- **WHEN** OLLAMA_USE_QUANTIZED=true in environment
- **THEN** system uses quantized model variant (e.g., llama3.1:8b-q4_0)
- **AND** it validates quantized model is available
- **AND** health check shows quantization status
- **AND** quantized models reduce memory footprint by ~50%

#### Scenario: Tree summarization for large contexts
- **WHEN** similarity_top_k > 10 chunks retrieved
- **THEN** query engine uses tree_summarize response mode
- **AND** it hierarchically summarizes chunks to fit context window
- **AND** it preserves key information through multi-stage summarization
- **AND** latency increases but OOM risk is eliminated

#### Scenario: Dynamic context window adjustment
- **WHEN** system detects available memory via Ollama health endpoint
- **THEN** it calculates safe context window (memory_available * 0.6)
- **AND** it adjusts OLLAMA_CONTEXT_WINDOW dynamically per request
- **AND** it logs context adjustments for monitoring

### Requirement: Embedding Model Benchmarking
The system SHALL provide benchmarking harness to compare embedding models on retrieval quality for SQL lineage queries.

#### Scenario: Benchmark test suite execution
- **WHEN** benchmark command is run with model list
- **THEN** system runs fixed set of 20+ lineage queries
- **AND** for each query, it retrieves top-5 chunks using each model
- **AND** it compares retrieved chunks against labeled ground truth
- **AND** it calculates Precision@5, Recall@5, MRR, and latency

#### Scenario: Ground truth dataset
- **WHEN** benchmark suite initializes
- **THEN** it loads test queries with expected results from JSON file
- **AND** each query has list of expected file paths and entity names
- **AND** ground truth is manually curated for SQL lineage domain
- **AND** dataset covers tables, views, columns, procedures, CTEs

#### Scenario: Benchmark result reporting
- **WHEN** benchmark completes
- **THEN** it outputs markdown report with comparison table
- **AND** report includes per-model metrics and ranking
- **AND** it highlights best model for each metric
- **AND** it saves results to `docs/benchmarks/EMBEDDING_RESULTS_[date].md`

#### Scenario: Model comparison test
- **WHEN** comparing nomic-embed-text vs alternatives (all-minilm-l6-v2, bge-small-en)
- **THEN** benchmark measures retrieval quality on same corpus
- **AND** it measures embedding latency per model
- **AND** it measures memory footprint
- **AND** recommendation is based on quality-latency-size tradeoff

### Requirement: Semantic Query Caching
The system SHALL cache query results using semantic similarity matching, not just exact hash matching.

#### Scenario: Similarity-based cache lookup
- **WHEN** new query is received
- **THEN** system embeds query text
- **AND** it searches dedicated query_cache Qdrant collection
- **AND** if similar query found with score >= 0.95, return cached result
- **AND** cache hit is logged with similarity score

#### Scenario: Cache storage with embedding
- **WHEN** query completes successfully
- **THEN** system stores result in Redis with hash key
- **AND** it also stores query embedding in Qdrant query_cache collection
- **AND** Qdrant payload includes Redis cache key and timestamp
- **AND** cache TTL is 1 hour

#### Scenario: Cache invalidation on reindex
- **WHEN** new documents are indexed or collection is reindexed
- **THEN** system clears all query cache entries
- **AND** it deletes Redis keys matching "query:*" pattern
- **AND** it truncates query_cache Qdrant collection
- **AND** it logs cache invalidation event

### Requirement: Batch Embedding Generation
The system SHALL support batch embedding requests to reduce Ollama API overhead.

#### Scenario: Batch embedding with cache check
- **WHEN** system needs to embed N texts
- **THEN** it checks Redis cache for all texts in parallel
- **AND** it identifies uncached texts
- **AND** it calls Ollama embedding API only for uncached texts
- **AND** it merges cached and new embeddings in original order

#### Scenario: Batch size optimization
- **WHEN** batch contains > 50 texts
- **THEN** system splits into sub-batches of 50
- **AND** it processes sub-batches sequentially
- **AND** it respects Ollama rate limits
- **AND** total latency is reduced vs individual calls

#### Scenario: Cache warming on startup
- **WHEN** system starts with USE_CACHE_WARMING=true
- **THEN** it loads most common entity names from graph
- **AND** it generates embeddings for top 1000 entities
- **AND** it pre-populates embedding cache
- **AND** subsequent queries benefit from warm cache

### Requirement: HNSW Index Tuning
The system SHALL support tunable HNSW parameters for Qdrant collections to optimize retrieval quality and speed.

#### Scenario: Collection creation with HNSW config
- **WHEN** Qdrant collection is created
- **THEN** system reads QDRANT_HNSW_EF_CONSTRUCT environment variable (default: 100)
- **AND** it reads QDRANT_HNSW_M environment variable (default: 16)
- **AND** it passes HNSW config to Qdrant create_collection API
- **AND** health check shows HNSW configuration

#### Scenario: Dataset-specific tuning
- **WHEN** corpus size < 10k vectors
- **THEN** recommended config is ef_construct=100, m=16
- **WHEN** corpus size 10k-100k vectors
- **THEN** recommended config is ef_construct=150, m=24
- **WHEN** corpus size > 100k vectors
- **THEN** recommended config is ef_construct=200, m=32

#### Scenario: Index maintenance
- **WHEN** REINDEX_SCHEDULE cron trigger fires
- **THEN** system triggers Qdrant optimization API
- **AND** it logs index statistics (vector count, memory usage)
- **AND** it validates search performance after optimization

### Requirement: Prompt Template Management
The system SHALL use centralized, validated prompt templates with hallucination safeguards and citation requirements.

#### Scenario: Template-based prompt construction
- **WHEN** RAG query is executed
- **THEN** system selects appropriate template (LINEAGE_QUERY, GRAPH_QUERY, etc.)
- **AND** it validates all required template variables are provided
- **AND** it formats prompt with context and question
- **AND** prompt includes explicit citation requirements

#### Scenario: Hallucination prevention rules
- **WHEN** LINEAGE_QUERY template is used
- **THEN** prompt instructs LLM to cite sources as [file:line]
- **AND** it instructs LLM to say "Information not available" if context lacks data
- **AND** it prohibits inference or assumption of relationships
- **AND** it requires every claim to reference context

#### Scenario: Token budget enforcement
- **WHEN** prompt is constructed
- **THEN** system allocates token budget: 5% system, 10% project context, 60% retrieval, 5% question, 20% response
- **AND** it trims each component to fit allocation
- **AND** it prioritizes highest-relevance context chunks
- **AND** total prompt never exceeds OLLAMA_CONTEXT_WINDOW

#### Scenario: Project context selection
- **WHEN** project context is available
- **THEN** system limits to 5-10 most relevant items
- **AND** it uses semantic similarity to rank context items
- **AND** it includes only items relevant to current query
- **AND** it logs context item selection for debugging

### Requirement: Embed Calls Must Include Model Parameter
The system SHALL require an explicit model parameter for all embedding calls.

#### Scenario: Legacy ingestion embeds supply model
- **WHEN** legacy ingestion calls `embed()` for code chunks
- **THEN** the call includes the embedding model from configuration
- **AND** missing/invalid model triggers a clear error before the Ollama request
- **AND** ingestion continues to process remaining chunks even if one embed fails

