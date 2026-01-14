# Implementation Guide: Zero-Cost Hybrid Lineage Enhancements (COMPLETE)

## Quick Reference

**Change ID**: `enhance-zero-cost-hybrid-lineage`
**Status**: ✅ Validated (strict mode)
**Tasks**: 93 total across 10 phases
**Specs**: llm-service, api-endpoints, hybrid-search (new), storage-reliability, code-parsing (new)

## Executive Summary

This is a **comprehensive modernization** delivering production-ready features from RFC-4.0 while cleaning up technical debt:

✅ **OpenRouterService** - Dedicated LLM service with free-tier enforcement  
✅ **Plugin Architecture** - Extensible parser system (add languages via .env)  
✅ **Tree-sitter Python** - Robust parsing with syntax-error tolerance  
✅ **Hybrid Search** - BM25 + semantic retrieval (+40-60% accuracy)  
✅ **Idempotency Protocol** - Clean re-ingestion (no ghost data)  
✅ **Code Consolidation** - Remove orphaned code, update docs  
✅ **SQL Dialect API** - Dynamic frontend configuration  
✅ **URN Standardization** - Cross-repository lineage support  

**Updated Models** (per request):
- ❌ Removed: `xiaomi/mimo-v2-flash`
- ✅ Added: `mistralai/devstral-2512:free` (code analysis specialist)

---

## Start Here: Phase 1 (Week 1)

### Critical Path - 22 Tasks ⚡

**1. OpenRouterService (10 tasks)**
```python
# src/services/inference_service.py - NEW FILE
class OpenRouterService:
    """Dedicated service for structured lineage inference."""
    
    FREE_TIER_MODELS = {
        "google/gemini-2.0-flash-exp:free",
        "mistralai/devstral-2512:free",  # 🆕 Code analysis
        "deepseek/deepseek-r1:free"
    }
    
    async def predict_lineage(
        self, code: str, context: list[str]
    ) -> list[LineageEdgeProposal]:
        # Strict JSON mode, fail-open error handling
        ...
```

**2. Idempotency (6 tasks)**
```python
# Before re-ingestion
await qdrant.delete_by_file_path("code_chunks", file_path)
await neo4j.purge_file_assets(file_path)
```

**3. Free-Tier Enforcement (6 tasks)**
```python
# In InferenceRouter
def _enforce_free_tier(self, model: str) -> str:
    if model not in FREE_TIER_MODELS:
        logger.warning(f"Downgrading {model} to free tier")
        return "google/gemini-2.0-flash-exp:free"
    return model
```

---

## Full Implementation Path

### Phase 2: Plugin Architecture (Week 2) 🛠️
**11 tasks** - Foundation for extensibility

```python
# src/ingestion/plugins/base.py
class LineagePlugin(ABC):
    @abstractmethod
    def supported_extensions(self) -> list[str]: ...
    
    @abstractmethod
    def parse(self, content: str) -> LineageResult: ...
```

Migrate existing parsers:
- `StandardSqlPlugin` (wraps sqlglot)
- `PythonAstPlugin` (wraps ast module)
- `JsonEnricherPlugin` (metadata only)

### Phase 3: Tree-sitter Python (Week 2-3) 🔨
**10 tasks** - Robust error-tolerant parsing

```python
# src/ingestion/plugins/python_treesitter.py
class PythonTreesitterPlugin(LineagePlugin):
    def parse(self, content: str) -> LineageResult:
        # Tolerates syntax errors, returns partial AST
        tree = self.parser.parse(bytes(content, "utf8"))
        return self._extract_lineage(tree)
```

### Phase 4: Hybrid Search (Week 3) 🔥
**7 tasks** - BM25 + semantic

```python
# Reciprocal Rank Fusion
results = await qdrant.hybrid_search(
    query_text="fact_trades",
    dense_vector=[...],
    fusion_weight=0.5  # Balance sparse + dense
)
```

### Phase 5-10: Additional Features
- **SQL Dialect API** (7 tasks)
- **URN Standardization** (7 tasks)
- **Code Consolidation** (10 tasks)
- **Documentation** (12 tasks)
- **Testing** (7 tasks)

---

## Key Design Decisions

### 1. Why OpenRouterService (not InferenceRouter extension)?
**Separation of Concerns**:
- `InferenceRouter` = General chat/RAG completions
- `OpenRouterService` = Structured lineage predictions (domain-specific)

Different needs:
- Prompts (lineage-specific vs general chat)
- Output parsing (typed `LineageEdgeProposal` vs text)
- Error handling (fail-open for lineage vs retry for chat)

### 2. Why Plugin Architecture?
**Extensibility without code changes**:
```env
# .env - Just add a module path!
LINEAGE_PLUGINS=src.ingestion.plugins.dbt_core.DbtManifestPlugin
```

**Before**: Modify `CodeParser` class (risky)  
**After**: Drop in plugin, update config (safe)

### 3. Why Tree-sitter?
**Real-world robustness**:
- Python's `ast.parse()` crashes on syntax errors
- Tree-sitter continues parsing (returns partial AST)
- Battle-tested in VSCode, Neovim

**Performance**: AST fallback for small files (no regression)

---

## Testing Strategy

```python
# tests/unit/services/test_openrouter_service.py
async def test_free_tier_enforcement():
    service = OpenRouterService(api_key="test")
    
    assert service._enforce_free_tier("gpt-4") == "google/gemini-2.0-flash-exp:free"
    assert service._enforce_free_tier("mistralai/devstral-2512:free") == "mistralai/devstral-2512:free"

# tests/integration/test_idempotency.py
async def test_file_shrinkage():
    # Ingest 10 chunks
    await ingest("file.sql", "..."  * 1000)
    assert await count_chunks("file.sql") == 10
    
    # Shrink to 5 chunks
    await ingest("file.sql", "..." * 500)
    assert await count_chunks("file.sql") == 5  # No ghosts!
```

---

## Documentation Updates

**Must Update**:
1. `ARCHITECTURE.md` - Plugin diagrams, OpenRouterService
2. `API_REFERENCE.md` - New endpoints
3. `DEPLOYMENT_GUIDE.md` - Qdrant upgrade, tree-sitter install
4. `PLUGIN_DEVELOPMENT_GUIDE.md` - **NEW** - How to create parsers
5. `TROUBLESHOOTING.md` - Plugin errors, idempotency issues

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| OpenRouter rate limits | Circuit breaker + Ollama fallback |
| Tree-sitter compile fails | Pre-compiled binaries + AST fallback |
| Plugin errors | Graceful degradation, skip bad plugins |
| Qdrant upgrade downtime | Backward compatible, dense-only fallback |

---

## Success Metrics

- **Cost**: $0 (free-tier enforcement working)
- **Search**: +40-60% Precision@5 vs dense-only
- **Idempotency**: 100% test pass rate
- **Extensibility**: <2 hours to add new parser

---

## Validation

```bash
$ openspec validate enhance-zero-cost-hybrid-lineage --strict
Change 'enhance-zero-cost-hybrid-lineage' is valid

$ openspec list | grep enhance
enhance-zero-cost-hybrid-lineage      0/93 tasks
```

---

## Next Steps

**Start NOW**:
```bash
# 1. Review full proposal
cat openspec/changes/enhance-zero-cost-hybrid-lineage/proposal.md

# 2. Check all 93 tasks
cat openspec/changes/enhance-zero-cost-hybrid-lineage/tasks.md

# 3. Read design decisions
cat openspec/changes/enhance-zero-cost-hybrid-lineage/design.md

# 4. Begin Phase 1 (OpenRouterService + Idempotency)
```

**This is a comprehensive architectural upgrade** - not just adding features, but modernizing the codebase foundation. 🚀
