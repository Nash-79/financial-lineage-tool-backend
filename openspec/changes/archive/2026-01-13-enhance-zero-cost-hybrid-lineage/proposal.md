# Change: Enhance Zero-Cost Hybrid Lineage System

## Why

The current implementation provides solid foundation for hybrid lineage (deterministic + LLM inference) but lacks critical production-readiness features identified in the RFC-4.0 "Zero-Cost Polyglot Knowledge Graph" design:

1. **Cost Control Gap**: No enforcement of free-tier models - risk of incurring charges from OpenRouter/Groq
2. **Search Quality Gap**: Qdrant uses only dense vectors - missing BM25 sparse vectors for keyword precision in "Deep Search"
3. **Data Integrity Gap**: No idempotency protocol - re-ingesting files leaves ghost chunks and stale nodes
4. **Dialect Flexibility Gap**: Frontend cannot discover available SQL dialects dynamically - blocks multi-database support
5. **URN Inconsistency**: Mixed ID schemes across graph nodes - complicates cross-repository lineage

These gaps prevent the system from delivering on the "Zero Marginal Cost" and "Enterprise-Grade" promises in production.

## What Changes

**Cost Control (Zero-Cost Guarantee)**
- Create dedicated `OpenRouterService` for zero-cost LLM routing
- Implement free-tier model whitelist enforcement with routing guard
- Add `predict_lineage()` method for structured edge proposals
- Automatic downgrade to Gemini Flash if non-free model requested
- Log warnings and metrics when downgrade occurs
- Use strict JSON mode for reliable parsing

**Search Quality (Hybrid Retrieval)**
- Upgrade Qdrant collections to support sparse + dense vectors (BM25 + semantic)
- Implement Reciprocal Rank Fusion for combined search results
- Add `hybrid_search()` method to `QdrantLocalClient`
- Configure existing collections for backward compatibility

**Data Integrity (Idempotency Protocol)**
- Add `delete_by_file_path()` to `QdrantLocalClient` for vector cleanup
- Add `purge_file_assets()` to Neo4j service for graph cleanup
- Implement "purge-then-write" pattern in ingestion pipeline
- Ensure re-ingestion produces clean slate state

**Post-Ingestion Validation & Gap Detection**
- Add validation agent that runs after ingestion to verify parsing correctness
- Detect gaps between parsed outputs and graph state (missing nodes/edges)
- Capture validation output in ingestion logs for auditability

**Knowledge Graph Enrichment Agent**
- Add KG agent that proposes new edges using free-tier OpenRouter Devstral
- Allow agent to write edges directly to Neo4j with LLM metadata
- Record agent proposals and decisions in ingestion logs
- Capture a full Neo4j snapshot before ingestion (stored locally) for comparison

**Project Linking + Run-Scoped Artifacts**
- Add project-to-project links for cross-project lineage context
- Store KG snapshots, chunk outputs, and validation artifacts under run directories
- Scope Neo4j snapshot exports by project and file paths

**Dialect Discovery**
- Expose `GET /api/v1/config/sql-dialects` endpoint
- Return list of enabled dialects from backend registry
- Support frontend dialect dropdown population
- Include display name, sqlglot key, default flag

**URN Standardization**
- Standardize on `urn:li:` format across all node IDs
- Update `_generate_id()` in graph extractor
- Add URN parsing/validation utilities
- Document URN schema in project.md

**Modular Parser Architecture (Extensibility)**
- Create `LineagePlugin` abstract base class for parser plugins
- Implement plugin registry with dynamic loading from `.env`
- Migrate existing SQL, Python, JSON parsers to plugin pattern
- Support `supported_extensions()` and `parse()` interface
- Enable drop-in support for new languages (dbt, Airflow, Spark)

**Robust Python Parsing (Tree-sitter)**
- Integrate tree-sitter-python for syntax-error-tolerant parsing
- Handle partial/malformed Python files gracefully
- Extract classes, functions, imports with better accuracy
- Support Python 3.8-3.12 syntax variations
- Fallback to AST parser for simple files (performance)

**Code Consolidation & Cleanup (Technical Debt)**
- Remove orphaned/duplicate code from previous iterations
- Consolidate `InferenceRouter` and new `OpenRouterService` patterns
- Deprecate old prompt templates in favor of plugin system
- Remove unused imports and dead code paths
- Standardize error handling patterns across services
- Update all documentation to reflect new architecture

## Impact

- **Affected specs**: `llm-service`, `api-endpoints`, `hybrid-search` (new), `storage-reliability`, `code-parsing` (new), `data-organization`
- **Affected specs (new)**: `logging` (ingestion logs + validation/agent outputs)
- **Affected code**:
  - `src/services/inference_service.py` - NEW OpenRouterService
  - `src/models/inference.py` - NEW LineageEdgeProposal model
  - `src/llm/inference_router.py` - free-tier guard integration
  - `src/services/qdrant_service.py` - hybrid search, idempotency
  - `src/knowledge_graph/neo4j_client.py` - purge method
  - `src/api/routers/config.py` - dialect discovery endpoint
  - `src/ingestion/graph_extractor.py` - URN generation
  - `src/ingestion/plugins/base.py` - NEW plugin architecture
  - `src/ingestion/plugins/sql_standard.py` - NEW SQL plugin
  - `src/ingestion/plugins/python_treesitter.py` - NEW tree-sitter parser
  - `src/services/validation_agent.py` - NEW parsing validation agent
  - `src/services/kg_enrichment_agent.py` - NEW KG enrichment agent
  - `src/storage/graph_snapshot.py` - NEW Neo4j snapshot helper
  - `src/storage/duckdb_client.py` - Project link schema + file table rebuild
  - `src/api/routers/projects.py` - Project link endpoints
  - `src/api/routers/ingest.py` - Run-scoped ingestion artifacts
  - `.env.example` - plugin registry configuration
- **Breaking changes**: None (all changes are additive or internal)
- **Database migrations**: Qdrant collection upgrade (backward compatible)
- **Frontend impact**: New dialect dropdown (requires frontend PR)
