# Implementation Tasks

## 1. Free-Tier Model Enforcement
- [x] 1.1 Define `FREE_TIER_MODELS` constant in `src/llm/inference_router.py`
- [x] 1.2 Implement `_enforce_free_tier(model: str) -> str` method
- [x] 1.3 Add enforcement to `_generate_cloud()` method
- [x] 1.4 Add enforcement to `_generate_with_model()` method
- [x] 1.5 Update config to document free-tier models in `.env.example`
- [x] 1.6 Add unit tests for model downgrade logic

## 2. Hybrid Search (Qdrant)
- [x] 2.1 Update `create_collection()` to support sparse vectors (BM25)
- [x] 2.2 Add `enable_hybrid: bool` parameter with default `True`
- [x] 2.3 Implement `search_sparse()` method for BM25 keyword search
- [x] 2.4 Implement `hybrid_search()` with Reciprocal Rank Fusion
- [x] 2.5 Add `_fuse_results()` helper for RRF algorithm
- [x] 2.6 Update existing collection creation calls (backward compatible)
- [x] 2.7 Add integration tests for hybrid search

## 3. Idempotency Protocol
- [x] 3.1 Implement `delete_by_file_path()` in `QdrantLocalClient`
- [x] 3.2 Implement `purge_file_assets()` in Neo4j service
- [x] 3.3 Add `_purge_before_ingest()` to ingestion pipeline
- [x] 3.4 Update `ingest_file()` to call purge before processing
- [x] 3.5 Update `ingest_repository()` to purge per-file
- [x] 3.6 Add idempotency integration tests (ingest → modify → re-ingest)
- [x] 3.7 Document idempotency guarantees in API docs
- [x] 3.8 Add post-ingestion artifact validation cleanup

## 4. SQL Dialect Discovery API
- [x] 4.1 Create `src/api/routers/config.py` if not exists
- [x] 4.2 Define `SQLDialect` Pydantic model (id, display_name, sqlglot_key, is_default)
- [x] 4.3 Implement `GET /api/v1/config/sql-dialects` endpoint
- [x] 4.4 Add dialect registry to DuckDB (or in-memory for MVP)
- [x] 4.5 Populate registry with initial dialects (tsql, postgres, mysql, duckdb, fabric, spark)
- [x] 4.6 Add OpenAPI schema documentation
- [x] 4.7 Add unit tests for dialect endpoint

## 5. URN Standardization
- [x] 5.1 Document URN schema in `openspec/project.md`
- [x] 5.2 Create `src/utils/urn.py` with parsing/validation utilities
- [x] 5.3 Define URN format: `urn:li:{entity_type}:{project_id}:{asset_path}`
- [x] 5.4 Update `_generate_id()` in graph extractor to use URN format
- [x] 5.5 Add backward compatibility for existing IDs (optional migration script)
- [x] 5.6 Update lineage inference to use URNs
- [x] 5.7 Add URN validation tests

## 6. Documentation & Testing
- [x] 6.1 Update API_REFERENCE.md with new endpoints
- [x] 6.2 Update DEPLOYMENT_GUIDE.md with Qdrant upgrade notes
- [x] 6.3 Add hybrid search usage examples
- [x] 6.4 Update TROUBLESHOOTING.md with idempotency troubleshooting
- [x] 6.5 Run full integration test suite
- [x] 6.6 Validate OpenSpec change with `openspec validate enhance-zero-cost-hybrid-lineage --strict`

## 6. OpenRouterService Implementation
- [x] 6.1 Create `src/services/inference_service.py` module
- [x] 6.2 Implement `OpenRouterService` class with httpx async client
- [x] 6.3 Add `predict_lineage(code_snippet, context_nodes)` method
- [x] 6.4 Implement routing guard with `FREE_TIER_MODELS` validation
- [x] 6.5 Add strict JSON mode request configuration
- [x] 6.6 Implement error handling (429, 503, JSON parse errors)
- [x] 6.7 Create `LineageEdgeProposal` Pydantic model in `src/models/inference.py`
- [x] 6.8 Add unit tests for OpenRouterService
- [x] 6.9 Add integration tests with mocked OpenRouter API
- [x] 6.10 Update dependency injection container to include OpenRouterService

## 7. Plugin Architecture
- [x] 7.1 Create `src/ingestion/plugins/base.py` with `LineagePlugin` ABC
- [x] 7.2 Define `LineageResult` dataclass for standardized output
- [x] 7.3 Create plugin registry in `src/ingestion/plugin_registry.py`
- [x] 7.4 Implement `PluginLoader` for dynamic loading from `.env`
- [x] 7.5 Document `LINEAGE_PLUGINS` and `LINEAGE_PLUGIN_CONFIG_JSON` in `.env.example`
- [x] 7.6 Migrate existing `CodeParser.parse_sql()` to `StandardSqlPlugin`
- [x] 7.7 Migrate existing `CodeParser.parse_python()` to legacy `PythonAstPlugin`
- [x] 7.8 Migrate existing `CodeParser.parse_json()` to `JsonEnricherPlugin`
- [x] 7.9 Update ingestion pipeline to use plugin registry
- [x] 7.10 Add plugin test harness and regression tests
- [x] 7.11 Document plugin development guide in docs/

## 8. Tree-sitter Python Parser
- [x] 8.1 Add `tree-sitter` and `tree-sitter-python` to requirements.txt
- [x] 8.2 Create `src/ingestion/plugins/python_treesitter.py`
- [x] 8.3 Implement tree-sitter initialization and language loading
- [x] 8.4 Implement `parse()` method with syntax-error tolerance
- [x] 8.5 Add extraction for classes, functions, imports
- [x] 8.6 Add SQL reference extraction from string literals
- [x] 8.7 Add AST fallback for small/well-formed files (performance optimization)
- [x] 8.8 Add support for Python 3.8-3.12 syntax variations
- [x] 8.9 Add unit tests with malformed Python samples
- [x] 8.10 Add performance benchmark comparing tree-sitter vs AST

## 9. Code Consolidation & Cleanup
- [x] 9.1 Audit codebase for orphaned/unused code from previous iterations
- [x] 9.2 Remove duplicate prompt templates (consolidate to plugin system)
- [x] 9.3 Remove unused imports across all modules
- [x] 9.4 Consolidate error handling patterns (use consistent exceptions)
- [x] 9.5 Remove dead code paths in `code_parser.py`
- [x] 9.6 Deprecate old `_fallback_regex_parse()` in favor of plugin fallback
- [x] 9.7 Clean up `InferenceRouter` vs `OpenRouterService` overlaps
- [x] 9.8 Standardize logging format across all services
- [x] 9.9 Remove obsolete configuration options from config.py
- [x] 9.10 Run linter (ruff) and formatter (black) on entire codebase

## 10. Documentation & Verification
- [x] 10.1 Update API_REFERENCE.md with all new endpoints
- [x] 10.2 Update DEPLOYMENT_GUIDE.md with:
   - Qdrant hybrid search upgrade notes
   - Tree-sitter Python installation
   - Plugin configuration examples (`.env`)
- [x] 10.3 Create PLUGIN_DEVELOPMENT_GUIDE.md for new parser plugins
- [x] 10.4 Update ARCHITECTURE.md with plugin architecture diagrams
- [x] 10.5 Update TROUBLESHOOTING.md with:
   - Idempotency troubleshooting
   - Plugin loading errors
   - Tree-sitter installation issues
- [x] 10.6 Add code examples for OpenRouterService usage
- [x] 10.7 Add code examples for hybrid search
- [x] 10.8 Update README.md with new features
- [x] 10.9 Update openspec/project.md with URN format and conventions
- [x] 10.10 Run full integration test suite
- [x] 10.11 Validate all documentation links are working
- [x] 10.12 Validate OpenSpec with `openspec validate enhance-zero-cost-hybrid-lineage --strict`

## 11. Validation + KG Agents
- [x] 11.1 Create validation agent to verify parsing correctness and gap detection
- [x] 11.2 Run validation agent after ingestion per file/batch
- [x] 11.3 Capture validation output in ingestion logs
- [x] 11.4 Implement Neo4j pre-ingestion snapshot (project/file-scoped) stored under `/data/{project}/{run}/KG`
- [x] 11.5 Reference snapshot path in ingestion logs
- [x] 11.6 Create KG enrichment agent using OpenRouter Devstral free-tier model
- [x] 11.7 Write KG agent edges directly to Neo4j with LLM metadata
- [x] 11.8 Log KG agent proposals/results in ingestion logs
- [x] 11.9 Add unit tests for validation agent and KG agent behaviors
- [x] 11.10 Document validation/KG agent behavior and log artifacts
- [x] 11.11 Add post-ingestion Neo4j snapshot

## 12. Project Linking + Data Organization
- [x] 12.1 Add DuckDB v6 migration to rebuild files table without PK and refresh macros
- [x] 12.2 Create `project_links` table and store layer support
- [x] 12.3 Add project link API endpoints and Neo4j project link helpers
- [x] 12.4 Align `/ingest` artifacts with run directory (`chunks/`, `validations/`, `KG/`)
- [x] 12.5 Update data-organization spec for chunks, validations, and macro signatures
- [x] 12.6 Update API docs for project links and ingest response metadata
- [x] 12.7 Capture embeddings artifacts under run directory
