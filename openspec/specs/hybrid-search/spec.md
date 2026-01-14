# hybrid-search Specification

## Purpose
TBD - created by archiving change enhance-zero-cost-hybrid-lineage. Update Purpose after archive.
## Requirements
### Requirement: Sparse + Dense Vector Storage
The system SHALL support hybrid vector search combining BM25 (sparse) and semantic (dense) embeddings for improved retrieval accuracy.

#### Scenario: Collection creation with hybrid vectors
- **WHEN** creating a new Qdrant collection
- **THEN** the collection SHALL support both dense vectors (768-dim, cosine similarity)
- **AND** sparse vectors (BM25 keyword matching)
- **AND** the `enable_hybrid` parameter defaults to `True`

#### Scenario: Dense-only fallback
- **WHEN** creating a collection with `enable_hybrid=False`
- **THEN** only dense vectors are configured
- **AND** BM25 functionality is disabled

#### Scenario: Backward compatibility
- **WHEN** existing collections lack sparse vector support
- **THEN** the system continues to function with dense-only search
- **AND** hybrid search methods gracefully fall back to dense-only mode

### Requirement: Hybrid Search with Reciprocal Rank Fusion
The system SHALL combine sparse (BM25) and dense (semantic) search results using Reciprocal Rank Fusion (RRF).

#### Scenario: Hybrid search execution
- **WHEN** performing a hybrid search query
- **THEN** the system executes two parallel searches:
  - Sparse search (BM25) on text content
  - Dense search (semantic) on vector embeddings
- **AND** combines results using RRF algorithm
- **AND** returns top N fused results ranked by combined score

#### Scenario: Fusion weight configuration
- **WHEN** performing hybrid search with `fusion_weight` parameter
- **THEN** fusion_weight=0.0 prioritizes sparse (keyword) results
- **AND** fusion_weight=1.0 prioritizes dense (semantic) results
- **AND** fusion_weight=0.5 balances both equally (default)

#### Scenario: Query text embedding
- **WHEN** hybrid search is requested with query text
- **THEN** the system generates dense embedding using Ollama nomic-embed-text
- **AND** uses raw text for BM25 sparse search
- **AND** both searches are executed concurrently

### Requirement: BM25 Sparse Search
The system SHALL support keyword-based search using BM25 algorithm for exact term matching.

#### Scenario: Sparse search on text fields
- **WHEN** performing sparse search with query text
- **THEN** Qdrant indexes text content using BM25
- **AND** returns results ranked by keyword relevance
- **AND** exact term matches receive higher scores

#### Scenario: Sparse search with filters
- **WHEN** sparse search includes metadata filters (e.g., file_path)
- **THEN** results are filtered before ranking
- **AND** only matching documents are scored

### Requirement: Search Result Fusion
The system SHALL implement Reciprocal Rank Fusion (RRF) to merge sparse and dense search results.

#### Scenario: RRF algorithm
- **WHEN** combining sparse and dense results
- **THEN** for each result, compute RRF score = 1/(k + rank)
- **AND** k=60 (standard RRF constant)
- **AND** sum weighted RRF scores: `(1-w)*sparse_score + w*dense_score`
- **AND** re-rank all results by final score

#### Scenario: Deduplication
- **WHEN** the same document appears in both sparse and dense results
- **THEN** the system combines its scores (not duplicate)
- **AND** returns single entry with fused score

#### Scenario: Result count
- **WHEN** requesting N results from hybrid search
- **THEN** the system retrieves 2*N results from each search
- **AND** applies fusion to the combined pool
- **AND** returns top N after fusion

### Requirement: Performance and Caching
The system SHALL optimize hybrid search for low latency and resource efficiency.

#### Scenario: Concurrent sparse and dense search
- **WHEN** hybrid search is executed
- **THEN** sparse and dense searches run in parallel (async)
- **AND** total latency approximates max(sparse_latency, dense_latency)
- **AND** not sum of both

#### Scenario: Embedding cache
- **WHEN** generating dense embedding for query text
- **THEN** check Redis cache first
- **AND** use cached embedding if available
- **AND** only call Ollama on cache miss

#### Scenario: Query performance target
- **WHEN** hybrid search is executed on collection with <10k vectors
- **THEN** search completes within 500ms (p95)
- **AND** returns accurate top-k results

