# Specification: LLM Service

## ADDED Requirements

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
