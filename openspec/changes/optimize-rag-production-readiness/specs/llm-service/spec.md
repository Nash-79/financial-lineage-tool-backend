## ADDED Requirements

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

## MODIFIED Requirements

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
