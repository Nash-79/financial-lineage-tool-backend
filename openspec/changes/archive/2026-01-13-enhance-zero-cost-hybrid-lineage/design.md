# Technical Design

## Context

This change enhances the existing hybrid lineage system (deterministic + LLM inference) with production-readiness features from RFC-4.0. The system already has `InferenceRouter`, `LineageInferenceService`, and `QdrantLocalClient` in place - this change extends rather than replaces them.

**Key Constraints:**
- Zero marginal cost requirement (free-tier models only)
- Backward compatibility with existing Qdrant collections
- No breaking API changes
- Support multi-dialect SQL parsing

## Goals

**Primary:**
1. Guarantee zero-cost inference via free-tier model enforcement
2. Improve search quality with hybrid (BM25 + semantic) retrieval
3. Ensure data integrity via idempotent ingestion

**Secondary:**
4. Enable dynamic SQL dialect discovery for frontend
5. Standardize node identifiers with URN format
6. Implement plugin architecture for extensible parsing
7. Add tree-sitter for robust Python parsing
8. Consolidate and clean up orphaned code

**Non-Goals:**
- YAML configuration files (stick with .env for simplicity)
- Automatic migration of existing node IDs (manual script provided)

## Decisions

### Decision 1: Create Dedicated OpenRouterService
**Choice:** Create `OpenRouterService` as a specialized service for lineage inference, separate from `InferenceRouter`

**Rationale:**
- **Separation of Concerns**: `InferenceRouter` handles general LLM routing for chat/RAG, while `OpenRouterService` specializes in structured lineage inference
- **Structured Output**: Lineage inference requires strict JSON mode and `LineageEdgeProposal` parsing - different from general chat completions
- **Domain-Specific Logic**: Lineage inference needs custom prompts, validation, and error handling tailored to graph construction
- **Future Extensibility**: May need to add features like multi-turn reasoning, self-consistency checks, or ensemble voting specific to lineage
- **Testing**: Easier to mock and test lineage-specific behavior separately

**Implementation:**
```python
# src/services/inference_service.py
class OpenRouterService:
    FREE_TIER_MODELS = {
        "google/gemini-2.0-flash-exp:free",
        "mistralai/mistral-7b-instruct:free",
        "mistralai/devstral-2512:free",  # Code analysis
        "meta-llama/llama-3.1-8b-instruct:free",
        "deepseek/deepseek-r1:free"
    }

    async def predict_lineage(
        self,
        code_snippet: str,
        context_nodes: list[str]
    ) -> list[LineageEdgeProposal]:
        model = self._enforce_free_tier(self.default_model)
        # Strict JSON mode, lineage-specific prompt
        response = await self._call_openrouter(
            prompt=self._build_lineage_prompt(code_snippet, context_nodes),
            model=model,
            response_format={"type": "json_object"}
        )
        return [LineageEdgeProposal(**e) for e in response["edges"]]
```

**Trade-offs:**
- **Pro**: Clean separation, easier to maintain domain logic
- **Pro**: `InferenceRouter` remains focused on chat/RAG routing
- **Con**: Small amount of code duplication (httpx client, error handling) - mitigated by shared base class or utilities

### Decision 2: Hybrid Search with Backward Compatibility
**Choice:** Make sparse vectors optional in `create_collection(enable_hybrid: bool = True)`

**Rationale:**
- Existing collections don't have sparse vectors configured
- Can't force re-index of all collections (data loss risk)
- New collections should default to hybrid, old collections degrade gracefully

**Implementation:**
- `hybrid_search()` attempts sparse+dense, falls back to dense-only if sparse unavailable
- Collection upgrade path: create new collection, migrate data, drop old (optional)

**Alternatives Considered:**
- **Force migration:** Too risky, breaks existing deployments
- **Dense-only forever:** Sacrifices search quality improvement

### Decision 3: Purge-Then-Write Idempotency
**Choice:** Execute deletes before inserts, fail ingestion if delete fails

**Rationale:**
- "Merge" strategies are complex and error-prone (what if file shrinks?)
- Delete-before-insert guarantees clean slate
- Transactional semantics prevent partial state

**Implementation:**
```python
async def ingest_file_idempotent(file_path: str, content: str):
    # 1. Purge phase
    await qdrant.delete_by_file_path("code_chunks", file_path)
    await neo4j.purge_file_assets(file_path)

    # 2. Insert phase (only if purge succeeded)
    chunks = await parse_and_chunk(content)
    await qdrant.upsert("code_chunks", chunks)
    await neo4j.ingest_lineage(chunks)
```

**Alternatives Considered:**
- **Upsert by chunk ID:** Doesn't handle shrinkage (leaves ghosts)
- **Soft delete with version:** Too complex, complicates queries

### Decision 4: SQL Dialect Registry in DuckDB
**Choice:** Store dialect list in DuckDB `sql_dialects` table

**Rationale:**
- Already using DuckDB for metadata
- No need for separate config file
- Easy to query from API endpoint
- Can add new dialects without code changes

**Schema:**
```sql
CREATE TABLE sql_dialects (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    sqlglot_key TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE
);
```

**Alternatives Considered:**
- **Hardcoded in code:** Not extensible
- **YAML config:** Adds dependency, harder to query
- **In-memory dict:** Lost on restart, can't persist user additions

### Decision 5: URN Format - Use LinkedIn Convention
**Choice:** `urn:li:{entity_type}:{project_id}:{asset_path}`

**Examples:**
- Table: `urn:li:dataset:finance_repo:prod_db.dim_users`
- Procedure: `urn:li:job:risk_repo:sp_calc_risk`
- File: `urn:li:file:etl_service:src/transform.py`

**Rationale:**
- `urn:li:` is industry standard (LinkedIn DataHub)
- More readable than `urn:fn:`
- Aligns with `docs/knowledge-graph/LINEAGE_OVERVIEW.md`

**Implementation:**
```python
# src/utils/urn.py
def generate_urn(entity_type: str, project_id: str, asset_path: str) -> str:
    return f"urn:li:{entity_type}:{project_id}:{asset_path}"

def parse_urn(urn: str) -> dict:
    parts = urn.split(":", 3)
    return {
        "scheme": parts[0],
        "namespace": parts[1],
        "entity_type": parts[2],
        "locator": parts[3]
    }
```

**Migration Strategy:**
- Add URN generation to `_generate_id()` in graph extractor
- Keep old IDs for backward compatibility (search both)
- Gradual migration script (optional)

## Risks & Trade-offs

### Risk 1: Qdrant Collection Upgrade
**Risk:** Existing collections lack sparse vectors, forcing dense-only fallback

**Mitigation:**
- Document upgrade path in DEPLOYMENT_GUIDE.md
- Provide migration script for new collections
- Hybrid search degrades gracefully to dense-only

**Trade-off:** Accept temporary dense-only operation vs. forcing downtime for migration

### Risk 2: Free-Tier Model Rate Limits
**Risk:** Gemini Flash has rate limits (15 RPM free tier), could cause 429 errors

**Mitigation:**
- Circuit breaker already in place in `InferenceRouter`
- Falls back to Ollama on rate limit
- Log warnings for monitoring

**Trade-off:** Occasional fallback to local model vs. incurring costs with paid tiers

### Risk 3: Idempotency Delete Performance
**Risk:** Deleting 1000+ chunks per file could be slow

**Mitigation:**
- Qdrant filter-based delete is efficient (indexed)
- Neo4j `DETACH DELETE` is optimized for graph cleanup
- Monitor ingestion latency metrics

**Trade-off:** Accept slight latency increase vs. data integrity guarantees

## Migration Plan

### Phase 1: Core Implementation (Week 1)
1. Free-tier enforcement in `InferenceRouter`
2. Idempotency methods (`delete_by_file_path`, `purge_file_assets`)
3. Integration into ingestion pipeline

### Phase 2: Hybrid Search (Week 2)
1. Update `create_collection()` for sparse+dense
2. Implement `hybrid_search()` with RRF
3. Add graceful fallback for existing collections

### Phase 3: API Extensions (Week 3)
1. SQL dialect registry in DuckDB
2. `/api/v1/config/sql-dialects` endpoint
3. Dialect validation in ingestion endpoints

### Phase 4: URN Standardization (Week 4)
1. URN utility module
2. Update `_generate_id()`
3. Optional migration script

**Rollback Plan:**
- All changes are additive or internal (no breaking API changes)
- Feature flags for hybrid search: `ENABLE_HYBRID_SEARCH=false` falls back to dense-only
- Idempotency can be disabled by skipping delete calls (not recommended)

## Open Questions

1. **Q:** Should we enforce free-tier at API level or only in router?
   **A:** Router only - keeps enforcement logic centralized

2. **Q:** How to handle Qdrant collections that need upgrade but can't be dropped?
   **A:** Provide migration script that creates new collection, copies data, swaps names

3. **Q:** Should URN migration be automatic or manual?
   **A:** Manual via script - automatic migration risks data consistency issues

4. **Q:** Do we need to expose hybrid search toggle in frontend?
   **A:** Not initially - backend auto-detects capability and falls back gracefully

### Decision 6: Plugin Architecture for Parsers
**Choice:** Implement plugin-based architecture with `LineagePlugin` ABC and `.env` configuration

**Rationale:**
- **Extensibility**: Adding new languages (dbt, Airflow DAGs, Terraform) shouldn't require modifying core ingestion logic
- **Maintainability**: Each parser is self-contained with clear interface contract
- **Testing**: Plugins can be tested independently with their own test suites
- **Configuration**: `.env` allows enabling/disabling parsers without code changes
- **Decouple from RFC Complexity**: Instead of building monolithic `CodeParser`, use small focused plugins

**Implementation:**
```python
# src/ingestion/plugins/base.py
class LineagePlugin(ABC):
    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """e.g., ['.sql', '.hql']"""
        pass

    @abstractmethod
    def parse(self, content: str, context: dict) -> LineageResult:
        """
        Returns:
            LineageResult with nodes, edges, external_refs
        """
        pass

# .env
LINEAGE_PLUGINS=src.ingestion.plugins.sql_standard.StandardSqlPlugin,src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin,src.ingestion.plugins.json_enricher.JsonEnricherPlugin
LINEAGE_PLUGIN_CONFIG_JSON={"src.ingestion.plugins.sql_standard.StandardSqlPlugin":{"default_dialect":"duckdb"},"src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin":{"prefer_ast_for_small_files":true}}
```

**Migration Strategy:**
1. Create plugin infrastructure (ABC, registry, loader)
2. Wrap existing `CodeParser` methods as plugins
3. Update ingestion pipeline to use plugin registry
4. Deprecate `CodeParser` class (mark for removal in next version)
5. Add new plugins (dbt, Airflow) as needed

**Alternatives Considered:**
- **Keep monolithic CodeParser**: Doesn't scale, hard to test individual parsers
- **Factory pattern only**: Less flexible than plugin system with external config

### Decision 7: Tree-sitter for Python Parsing
**Choice:** Use tree-sitter-python as primary Python parser, with AST fallback for performance

**Rationale:**
- **Syntax Error Tolerance**: Tree-sitter continues parsing after syntax errors, returning partial AST. Useful for incomplete/generated code.
- **Robustness**: Python's `ast` module crashes on syntax errors. Real-world codebases have malformed files, commented-out code, etc.
- **Version Compatibility**: Tree-sitter handles syntax variations (Python 3.8-3.12) more gracefully
- **Production Readiness**: Battle-tested in editors (VSCode, Neovim) - proven reliable
- **Performance**: For small files, AST fallback ensures no regression

**Implementation:**
```python
# src/ingestion/plugins/python_treesitter.py
class PythonTreesitterPlugin(LineagePlugin):
    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(Language('build/python.so', 'python'))

    def parse(self, content: str, context: dict) -> LineageResult:
        # Try AST first for small files (performance)
        if len(content) < 5000 and context.get("prefer_ast", False):
            try:
                return self._parse_with_ast(content)
            except SyntaxError:
                pass  # Fall through to tree-sitter

        # Parse with tree-sitter (tolerates errors)
        tree = self.parser.parse(bytes(content, "utf8"))
        return self._extract_lineage_from_tree(tree)
```

**Trade-offs:**
- **Pro**: Handles malformed code gracefully
- **Pro**: Better error recovery for production ingestion
- **Con**: Additional dependency (tree-sitter binary)
- **Con**: Slightly slower than AST for well-formed files (mitigated by fallback)

**Installation:**
```bash
pip install tree-sitter tree-sitter-python
```

### Decision 8: Code Consolidation & Cleanup
**Choice:** Include cleanup of orphaned code, duplicate logic, and documentation updates as part of this change

**Rationale:**
- **Technical Debt**: Previous RFC iterations left unused code paths, duplicate prompts, and stale docs
- **Single Source of Truth**: Plugin architecture deprecates old `CodeParser` monolith - clean transition
- **Maintainability**: Removing dead code reduces cognitive load for future developers
- **Documentation Accuracy**: Outdated docs mislead users - update holistically with architecture changes

**Cleanup Targets:**
1. **Orphaned Code**:
   - Remove unused `_fallback_regex_parse()` after plugin migration
   - Clean up duplicate prompt templates in `LineageInferenceService`
   - Remove old SQL dialect detection hacks

2. **Consolidation**:
   - Merge similar error handling patterns into shared utilities
   - Standardize logging format (structured logging with context)
   - Consolidate `InferenceRouter` and `OpenRouterService` shared code into base class

3. **Documentation**:
   - Update ARCHITECTURE.md with plugin architecture diagrams
   - Create PLUGIN_DEVELOPMENT_GUIDE.md for extensibility
   - Update API_REFERENCE.md with all new endpoints
   - Fix broken links in TROUBLESHOOTING.md

**Implementation Checklist:**
- [ ] Run linter (ruff) and formatter (black) on codebase
- [ ] Remove unused imports (automated with ruff)
- [ ] Audit `CodeParser` for dead paths
- [ ] Update all `.md` files referencing old architecture
- [ ] Validate documentation links with link checker

**Trade-offs:**
- **Pro**: Clean, maintainable codebase ready for future development
- **Pro**: Single coherent change captures all related work
- **Con**: Larger changeset, longer review time (mitigated by clear tasks list)

### Decision 9: Post-Ingestion Validation Agent
**Choice:** Run a validation agent immediately after ingestion to verify parsing correctness and detect gaps.

**Rationale:**
- Ensures deterministic parsers produce expected graph entities and relationships
- Highlights gaps where parsing misses entities or edges
- Produces a structured validation report for audit and troubleshooting

**Implementation:**
- Validation agent runs after ingestion completes per file (or per batch)
- Compares parsed results against Neo4j state for missing nodes/edges
- Writes validation summary into ingestion logs with per-file results

**Trade-offs:**
- **Pro**: Early detection of parsing issues
- **Con**: Additional latency after ingestion (acceptable for audit needs)

### Decision 10: KG Enrichment Agent with Free-Tier OpenRouter
**Choice:** Use OpenRouter Devstral (free tier) to propose KG edges and write directly to Neo4j.

**Rationale:**
- Devstral is optimized for code analysis and available on free tier
- Direct Neo4j writes allow immediate enrichment without human gating
- Capturing proposals in ingestion logs provides audit trail

**Implementation:**
- Use `OpenRouterService` with `mistralai/devstral-2512:free` as default
- Build context from newly ingested chunks plus current graph nodes
- Insert edges with metadata: source="llm", model name, confidence, status

**Trade-offs:**
- **Pro**: Improves lineage coverage without manual review
- **Con**: Potential false positives; mitigated via confidence thresholds

### Decision 11: Pre-Ingestion Neo4j Snapshot
**Choice:** Capture a full local Neo4j snapshot before ingestion and store it under `/data/{project_name}/KG`.

**Rationale:**
- Provides a consistent baseline for validation and auditing
- Enables diffing graph state before/after ingestion

**Implementation:**
- Export nodes/edges to a JSON artifact (per ingestion run)
- Store under `/data/{project_name}/KG/` with timestamped filename
- Include full node labels + properties and relationship types + properties
- Reference snapshot path in ingestion logs for traceability
