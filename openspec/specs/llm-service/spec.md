# llm-service Specification

## Purpose
TBD - created by archiving change dockerize-backend-with-huggingface. Update Purpose after archive.
## Requirements
### Requirement: Ollama Integration
The system SHALL use local Ollama installation for LLM operations and embeddings.

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

#### Scenario: Required models validation
- **WHEN** system starts
- **THEN** it checks llama3.1:8b model is available
- **AND** it checks nomic-embed-text model is available
- **AND** it provides clear error message if models are missing
- **AND** error message includes `ollama pull` commands

### Requirement: Embedding Generation
The system SHALL generate vector embeddings using Ollama nomic-embed-text model.

#### Scenario: Text embedding
- **WHEN** system needs to embed text
- **THEN** it calls Ollama embedding API
- **AND** it uses nomic-embed-text model
- **AND** it returns 768-dimensional vector
- **AND** embedding is deterministic for same input

#### Scenario: Batch embedding
- **WHEN** system needs to embed multiple texts
- **THEN** it processes texts individually (Ollama has no batch API)
- **AND** it respects rate limiting if needed
- **AND** it returns embeddings in same order as inputs

#### Scenario: Embedding caching
- **WHEN** system embeds previously seen text
- **THEN** it checks Redis cache first
- **AND** it returns cached embedding if available
- **AND** it only calls Ollama for cache misses
- **AND** cache is persisted in Redis

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
The system SHALL implement complete RAG pipeline using LlamaIndex abstractions.

#### Scenario: Vector store integration
- **WHEN** LlamaIndex needs vector storage
- **THEN** it uses QdrantVectorStore with code_chunks collection
- **AND** it stores 768-dimensional vectors
- **AND** it preserves document metadata
- **AND** it supports metadata filtering

#### Scenario: Query engine creation
- **WHEN** system creates query engine
- **THEN** it uses VectorStoreIndex.as_query_engine()
- **AND** it configures similarity_top_k=5
- **AND** it sets response_mode to "compact" or "tree_summarize"
- **AND** query engine is reusable across requests

#### Scenario: Response synthesis
- **WHEN** query engine generates response
- **THEN** it retrieves relevant context from vector store
- **AND** it constructs prompt with system message and context
- **AND** it calls Ollama LLM for generation
- **AND** it includes source citations in response

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
  - `google/gemini-2.0-flash-exp:free`
  - `mistralai/mistral-7b-instruct:free`
  - `mistralai/devstral-2512:free` (specialized for code analysis/generation)
  - `meta-llama/llama-3.1-8b-instruct:free`
  - `deepseek/deepseek-r1:free`

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

