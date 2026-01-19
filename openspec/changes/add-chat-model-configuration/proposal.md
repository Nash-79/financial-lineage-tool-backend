# Change: Add Unified Model Configuration API

## Why
All model assignments in the backend are currently hardcoded in multiple locations:
- `src/api/config.py` - Chat models (CHAT_*_PRIMARY/SECONDARY/TERTIARY_MODEL), embedding (EMBEDDING_MODEL), LLM (LLM_MODEL), FREE_TIER_MODELS
- `src/utils/constants.py` - DEFAULT_LLM_MODEL, DEFAULT_EMBEDDING_MODEL
- `src/llm/free_tier.py` - FREE_TIER_MODELS whitelist, DEFAULT_FREE_TIER_MODEL
- `src/services/kg_enrichment_agent.py` - DEFAULT_KG_MODEL

The frontend needs to be the single source of truth for ALL model configurations. This change makes the backend fully configuration-driven with zero hardcoded model assignments.

## Architectural Decisions

### Temperature Configuration Strategy
**Decision**: Temperatures will remain endpoint-level in `config.py` for now. Rationale:
- Temperatures are tuning parameters specific to chat endpoints, not to individual models
- Moving to per-model config adds complexity without clear benefit (most users won't adjust temperatures per model)
- Keeps config schema simpler and reduces DuckDB bloat
- Can be revisited in future if per-model temperature tuning is needed

### Startup Behavior
**Decision**: Backend will attempt to auto-seed default configurations on first startup (detected via empty `model_configs` table).
- If DuckDB table is empty, `ModelConfigService` initializes with defaults
- If frontend later calls `POST /api/v1/models/config/seed`, it will upsert (idempotent operation)
- Ensures backend never returns 503 for missing configs unless explicitly disabled by admin
- Frontend can still call seed endpoint to reset to defaults

### Error Handling for OpenRouter Discovery
**Decision**: OpenRouter model discovery failures will degrade gracefully.
- On API failure: Return cached results if available (Redis), empty list otherwise
- Log warnings but do not block service startup
- Frontend can retry discovery manually or use cached list
- If no models available, frontend can still configure models manually

### Rollback & Idempotency
**Decision**: DuckDB migrations are reversible; seed operations are idempotent.
- Seed endpoint can be called multiple times safely (upserts, never duplicates)
- Rollback: DuckDB migration snapshots (existing mechanism)
- If migration fails: Previous snapshot restored, service continues with old schema

## What Changes

### New API Endpoints
- **NEW**: `GET /api/v1/models/openrouter/free` - Fetches available free models from OpenRouter API
- **NEW**: `GET /api/v1/models/ollama` - Fetches available local Ollama models
- **NEW**: `GET /api/v1/models/config` - Returns ALL model configurations (chat, embedding, inference, edge creation)
- **NEW**: `POST /api/v1/models/config` - Upserts a model configuration (frontend maintains all configs)
- **NEW**: `DELETE /api/v1/models/config/{usage_type}/{priority}` - Removes a specific configuration
- **NEW**: `POST /api/v1/models/config/seed` - Seeds default configurations (one-time bootstrap or reset)

### Model Usage Types (Complete List)
| Usage Type | Provider | Current Hardcoded Location | Purpose |
|------------|----------|---------------------------|---------|
| `chat_deep` | OpenRouter | `config.CHAT_DEEP_*_MODEL` | Deep reasoning chat endpoint |
| `chat_semantic` | OpenRouter | `config.CHAT_SEMANTIC_*_MODEL` | Fast semantic search chat |
| `chat_text` | OpenRouter | `config.CHAT_TEXT_*_MODEL` | General text chat (no RAG) |
| `chat_graph` | OpenRouter | `config.CHAT_GRAPH_*_MODEL` | Graph-focused lineage chat |
| `chat_title` | OpenRouter | `config.CHAT_TITLE_*_MODEL` | Session title generation |
| `embedding` | Ollama | `config.EMBEDDING_MODEL` | Vector embeddings for RAG |
| `inference` | Ollama | `config.LLM_MODEL` | General Ollama inference |
| `kg_edge_creation` | OpenRouter | `kg_enrichment_agent.DEFAULT_KG_MODEL` | Knowledge graph edge proposals |

### Files Requiring Modification (Complete List from Codebase Analysis)

#### 1. Remove Hardcoded Models From `src/api/config.py`:
- Lines 64-78: `FREE_TIER_MODELS`, `_DEFAULT_FREE_TIER_MODELS`
- Lines 79-87: `DEFAULT_FREE_TIER_MODEL`, `INFERENCE_DEFAULT_MODEL`
- Lines 91-92: `LLM_MODEL`, `EMBEDDING_MODEL`
- Lines 107-151: All `CHAT_*_PRIMARY/SECONDARY/TERTIARY_MODEL` (15 variables)
- Lines 154-158: All `CHAT_*_TEMPERATURE` (5 variables)
- Lines 340-368: `get_chat_endpoint_models()` method
- Lines 371-379: `get_chat_endpoint_temperatures()` method

#### 2. Remove from `src/utils/constants.py`:
- Line 35: `DEFAULT_LLM_MODEL = "llama3.1:8b"`
- Line 36: `DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"`

#### 3. Deprecate `src/llm/free_tier.py` (entire file):
- `FREE_TIER_MODELS` set
- `DEFAULT_FREE_TIER_MODEL`
- `enforce_free_tier()` function → move validation to `ModelConfigService`

#### 4. Modify `src/services/kg_enrichment_agent.py`:
- Line 19: Remove `DEFAULT_KG_MODEL = "mistralai/devstral-2512:free"`
- Constructor: Accept model from `ModelConfigService.get_active_model("kg_edge_creation")`

#### 4b. Audit `src/services/agent_service.py`:
- Verify no hardcoded model constants
- If found, migrate to `ModelConfigService`

#### 4c. Audit `src/services/validation_agent.py`:
- Verify no hardcoded model constants
- If found, migrate to `ModelConfigService`

#### 5. Modify `src/services/chat_service.py`:
- Line 17: Remove import of `DEFAULT_FREE_TIER_MODEL, enforce_free_tier`
- Line 427: Replace `config.EMBEDDING_MODEL` with config service call
- Lines 634-640: Modify `_models_for_endpoint()` to read from `ModelConfigService`
- Lines 642-643: Modify `_temperature_for_endpoint()` to read from config service

#### 6. Modify `src/llm/inference_router.py`:
- Line 16: Remove import of `DEFAULT_FREE_TIER_MODEL, enforce_free_tier`
- Line 196: Replace `config.get_llm_model()` with `ModelConfigService.get_active_model("inference")`
- Line 243: Replace `config.INFERENCE_DEFAULT_MODEL` with config service call
- Lines 361-371: Replace `_enforce_free_tier()` with config service validation

#### 7. Modify `src/services/ingestion_pipeline.py`:
- Line 321: Replace `config.EMBEDDING_MODEL` with `ModelConfigService.get_active_model("embedding")`
- Line 354: Same replacement

#### 8. Modify `src/services/lineage_inference.py`:
- Line 136: Replace `config.EMBEDDING_MODEL` with config service call

#### 9. Modify `src/services/knowledge_inference.py`:
- Line 361: Replace `config.EMBEDDING_MODEL` with config service call

#### 10. Modify `src/api/main_local.py`:
- Line 205: Replace `config.LLM_MODEL, config.EMBEDDING_MODEL` with config service
- Lines 231, 253, 268, 350: Replace all `config.EMBEDDING_MODEL` references
- Add startup check that required model configs exist in DuckDB

#### 11. Modify `src/utils/exporters.py`:
- Line 271: Replace hardcoded `"nomic-embed-text"` with config service

#### 12. Startup Initialization in `src/api/main_local.py`:
- Add auto-seeding check on application startup
- If `model_configs` table is empty, trigger `ModelConfigService.seed_defaults()`
- Log migration status to console
- Ensure all required usage_types have at least one enabled config

### Configuration-Driven Architecture
- **REMOVED**: All hardcoded model assignments from backend code (see file list above)
- **REMOVED**: Hardcoded `FREE_TIER_MODELS` whitelist (replaced by dynamic list from OpenRouter)
- **DEPRECATED**: `src/llm/free_tier.py` - functionality moves to `ModelConfigService`
- **NEW**: DuckDB table `model_configs` stores ALL configurations
- **NEW**: `ModelConfigService` singleton with:
  - `get_active_model(usage_type)` - returns first enabled model for usage type
  - `get_fallback_chain(usage_type)` - returns ordered list of enabled models (for retry logic)
  - `validate_model(usage_type, model_id)` - validates model exists and is allowed for usage_type
- **RETAINED**: Endpoint-level temperatures in `config.py` (per-endpoint tuning)
- **NEW**: Auto-seeding on first startup: if `model_configs` table is empty, defaults are auto-populated
- **NEW**: Idempotent seed endpoint: can be called multiple times safely without duplication

### Frontend Responsibilities
- Frontend is the ONLY place where model configurations are created/updated
- Frontend calls `POST /api/v1/models/config/seed` on first setup to bootstrap defaults
- Frontend maintains enable/disable state, parameters, and priority ordering
- Frontend can call `GET /api/v1/models/openrouter/free` and `GET /api/v1/models/ollama` to show available models

## Impact Summary
- **Affected specs**: `llm-service`, `api-endpoints`
- **New files** (4):
  - `src/api/routers/models.py` - New REST API router
  - `src/services/model_config_service.py` - Configuration service singleton
  - `src/services/openrouter_model_service.py` - OpenRouter model discovery
  - `src/db/repositories/model_config_repository.py` - DuckDB repository
- **Modified files** (13):
  - `src/api/config.py` - Remove 20+ model variables (keep temperatures)
  - `src/utils/constants.py` - Remove 2 default model constants
  - `src/services/chat_service.py` - Use config service for models/fallback chains
  - `src/services/kg_enrichment_agent.py` - Use config service for KG model
  - `src/llm/inference_router.py` - Use config service for inference model
  - `src/services/ingestion_pipeline.py` - Use config service for embedding
  - `src/services/lineage_inference.py` - Use config service for embedding
  - `src/services/knowledge_inference.py` - Use config service for embedding
  - `src/api/main_local.py` - Auto-seed on startup, use config service
  - `src/utils/exporters.py` - Use config service for embedding
  - `src/services/agent_service.py` - Audit and migrate if needed
  - `src/services/validation_agent.py` - Audit and migrate if needed
  - DuckDB migration for `model_configs` table
- **Deprecated files** (1):
  - `src/llm/free_tier.py` - Functionality moves to ModelConfigService (mark for removal after migration)
- **Important Note**: Temperatures (`CHAT_*_TEMPERATURE` in config.py) are NOT migrated to config system. They remain endpoint-level configuration for now.

## Migration Path
1. Create DuckDB `model_configs` table with migration (reversible via snapshots)
2. Implement `ModelConfigRepository` and `ModelConfigService` with auto-seeding on empty table
3. Implement `OpenRouterModelService` and `OllamaModelService` with graceful error handling
4. Implement new API endpoints (`GET/POST/DELETE /api/v1/models/*`)
5. Update all 11+ files to use `ModelConfigService` instead of hardcoded values
6. Add startup check in `main_local.py` to verify required configs exist and auto-seed if empty
7. Frontend calls `/api/v1/models/config/seed` to reset to defaults (idempotent)
8. Remove/deprecate hardcoded model constants
9. Remove `src/llm/free_tier.py` after migration complete

## Rollback & Disaster Recovery
- **DuckDB Migration Rollback**: Use existing DuckDB snapshot mechanism (DUCKDB_SNAPSHOT_RETENTION_COUNT)
- **Seed Failure**: If seed endpoint fails, previous configs remain intact (upsert-based, not delete-based)
- **API Failure Recovery**: Model discovery failures don't block service startup; cached/empty list is returned
- **Database Corruption**: Restore from snapshot; service continues with previous schema version

## Future Frontend Proposal Needed
A separate frontend proposal (`add-unified-model-configuration-ui`) should implement:
- Model Configuration page with all 8 usage types
- OpenRouter model selector with descriptions
- Ollama model selector
- Parameter configuration (streaming, reasoning, temperature, max_tokens)
- Enable/disable toggles per configuration
- Seed/reset to defaults functionality
