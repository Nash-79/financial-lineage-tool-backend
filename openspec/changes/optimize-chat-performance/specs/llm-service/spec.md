## ADDED Requirements

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

## MODIFIED Requirements

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
