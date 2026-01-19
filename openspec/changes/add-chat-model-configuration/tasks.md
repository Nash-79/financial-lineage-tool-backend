# Tasks: Add Unified Model Configuration API

## 0. Pre-Implementation Decisions
- [ ] 0.1 Confirm architectural decision: Temperatures remain endpoint-level in config.py (not per-model)
- [ ] 0.2 Confirm architectural decision: Backend auto-seeds defaults on first startup (empty model_configs table)
- [ ] 0.3 Confirm architectural decision: OpenRouter discovery failures degrade gracefully (empty list, cached, or warning)
- [ ] 0.4 Audit `src/services/agent_service.py` and `src/services/validation_agent.py` for hardcoded models
- [ ] 0.5 Verify DuckDB snapshot mechanism works for rollback (test with existing migrations)

## 1. Database Schema
- [ ] 1.1 Create DuckDB migration for `model_configs` table with columns: id, usage_type, priority, model_id, model_name, provider, parameters (JSON), enabled, created_at, updated_at
- [ ] 1.2 Add unique constraint on (usage_type, priority) to prevent duplicate priority assignments
- [ ] 1.3 Define valid usage_types enum: chat_deep, chat_semantic, chat_text, chat_graph, chat_title, embedding, inference, kg_edge_creation

## 2. Repository Layer
- [ ] 2.1 Create `ModelConfigRepository` class in `src/db/repositories/model_config_repository.py`
- [ ] 2.2 Implement `get_all()` method returning all configurations
- [ ] 2.3 Implement `get_by_usage_type(usage_type)` method returning configs ordered by priority
- [ ] 2.4 Implement `upsert(config)` method for create/update operations
- [ ] 2.5 Implement `delete(usage_type, priority)` method for removing configurations
- [ ] 2.6 Implement `delete_all()` method for reset functionality
- [ ] 2.7 Implement `seed_defaults(configs)` method for bulk insert of default configurations

## 3. Model Discovery Services
- [ ] 3.1 Create `OpenRouterModelService` class in `src/services/openrouter_model_service.py`
- [ ] 3.2 Implement `fetch_free_models()` - calls OpenRouter `/api/v1/models`, filters by pricing.prompt == "0" and pricing.completion == "0"
- [ ] 3.3 Extract model metadata: id, name, description, context_length, supports_streaming, supports_reasoning
- [ ] 3.4 Add Redis caching (1-hour TTL) for OpenRouter response with graceful fallback if Redis unavailable
- [ ] 3.5 Implement error handling: if OpenRouter API fails, log warning and return cached list (if available) or empty list
- [ ] 3.6 Create `OllamaModelService` class in `src/services/ollama_model_service.py`
- [ ] 3.7 Implement `fetch_available_models()` - calls Ollama `/api/tags` to list local models
- [ ] 3.8 Extract Ollama model metadata: name, size, quantization, modified_at
- [ ] 3.9 Implement error handling: if Ollama API fails, log warning and return empty list (do not block service)

## 4. Model Configuration Service
- [ ] 4.1 Create `ModelConfigService` class in `src/services/model_config_service.py` as singleton
- [ ] 4.2 Implement `get_all_configs()` - returns all configurations grouped by usage_type
- [ ] 4.3 Implement `get_configs_for_usage(usage_type)` - returns ordered list by priority for specific usage
- [ ] 4.4 Implement `get_active_model(usage_type)` - returns first enabled model for a usage type (raises ValueError if none enabled)
- [ ] 4.5 Implement `get_fallback_chain(usage_type)` - returns all enabled models ordered by priority (for retry logic)
- [ ] 4.6 Implement `upsert_config(config)` - validates and saves configuration (raises ValueError if invalid)
- [ ] 4.7 Implement `validate_model(usage_type, model_id)` - checks if model is valid for usage_type
- [ ] 4.8 Implement `delete_config(usage_type, priority)` - removes configuration
- [ ] 4.9 Implement `seed_defaults()` - populates default configurations (idempotent, can be called multiple times)
- [ ] 4.10 Implement `reset_to_defaults()` - clears all and re-seeds defaults
- [ ] 4.11 Implement `_auto_seed_if_empty()` - checks if table is empty and auto-seeds on first run

## 5. API Router
- [ ] 5.1 Create `models.py` router in `src/api/routers/`
- [ ] 5.2 Implement `GET /api/v1/models/openrouter/free` - returns available free OpenRouter models
- [ ] 5.3 Implement `GET /api/v1/models/ollama` - returns available local Ollama models
- [ ] 5.4 Implement `GET /api/v1/models/config` - returns all configurations grouped by usage_type
- [ ] 5.5 Implement `POST /api/v1/models/config` - upserts a single configuration
- [ ] 5.6 Implement `DELETE /api/v1/models/config/{usage_type}/{priority}` - removes configuration
- [ ] 5.7 Implement `POST /api/v1/models/config/seed` - seeds default configurations (idempotent)
- [ ] 5.8 Register router in main FastAPI app

## 6. Remove Hardcoded Model Assignments (11+ files)

### 6.1 `src/api/config.py` - Remove model variables (keep temperatures)
- [ ] 6.1.1 Remove `_DEFAULT_FREE_TIER_MODELS` list (lines 64-71)
- [ ] 6.1.2 Remove `FREE_TIER_MODELS` variable (lines 72-78)
- [ ] 6.1.3 Remove `DEFAULT_FREE_TIER_MODEL`, `INFERENCE_DEFAULT_MODEL` (lines 79-87)
- [ ] 6.1.4 Remove `LLM_MODEL`, `EMBEDDING_MODEL` (lines 91-92)
- [ ] 6.1.5 Remove all `CHAT_*_PRIMARY/SECONDARY/TERTIARY_MODEL` (15 vars, lines 107-151)
- [ ] 6.1.6 **KEEP** all `CHAT_*_TEMPERATURE` variables (lines 154-158) - these remain endpoint-level
- [ ] 6.1.7 Remove `get_chat_endpoint_models()` method (lines 340-368) - now handled by ModelConfigService
- [ ] 6.1.8 **KEEP** `get_chat_endpoint_temperatures()` method (lines 371-379) - still used for endpoint-level temperatures

### 6.2 `src/utils/constants.py` - Remove default models
- [ ] 6.2.1 Remove `DEFAULT_LLM_MODEL = "llama3.1:8b"` (line 35)
- [ ] 6.2.2 Remove `DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"` (line 36)

### 6.3 `src/llm/free_tier.py` - Deprecate entire file
- [ ] 6.3.1 Move `enforce_free_tier()` logic to `ModelConfigService.validate_model()`
- [ ] 6.3.2 Remove `FREE_TIER_MODELS` set - replaced by dynamic list from OpenRouter
- [ ] 6.3.3 Remove `DEFAULT_FREE_TIER_MODEL` reference - replaced by config service
- [ ] 6.3.4 Add deprecation warning to top of file: "This module is deprecated. Use ModelConfigService instead."
- [ ] 6.3.5 Schedule for deletion in v2.0 or after 2 release cycles

### 6.4 `src/services/chat_service.py` - Use config service
- [ ] 6.4.1 Remove import of `DEFAULT_FREE_TIER_MODEL, enforce_free_tier` (line 17)
- [ ] 6.4.2 Add import of `ModelConfigService`
- [ ] 6.4.3 Replace `config.EMBEDDING_MODEL` with `ModelConfigService.get_active_model("embedding")` (line 427)
- [ ] 6.4.4 Modify `_models_for_endpoint()` to call `ModelConfigService.get_fallback_chain(usage_type)` instead of reading from config (lines 634-640)
- [ ] 6.4.5 Keep `_temperature_for_endpoint()` using `config.get_chat_endpoint_temperatures()` - temperatures remain endpoint-level (lines 642-643)

### 6.5 `src/services/kg_enrichment_agent.py` - Use config service
- [ ] 6.5.1 Remove `DEFAULT_KG_MODEL = "mistralai/devstral-2512:free"` (line 19)
- [ ] 6.5.2 Modify constructor to get model from `ModelConfigService.get_active_model("kg_edge_creation")`
- [ ] 6.5.3 Add error handling: if `get_active_model()` raises ValueError (no configs), log error and skip KG enrichment

### 6.5b `src/services/agent_service.py` - Audit and migrate if needed
- [ ] 6.5b.1 Search for hardcoded model constants (grep for "model", "llm", "embedding")
- [ ] 6.5b.2 If found, migrate to `ModelConfigService.get_active_model(usage_type)`
- [ ] 6.5b.3 Document any findings

### 6.5c `src/services/validation_agent.py` - Audit and migrate if needed
- [ ] 6.5c.1 Search for hardcoded model constants
- [ ] 6.5c.2 If found, migrate to `ModelConfigService.get_active_model(usage_type)`
- [ ] 6.5c.3 Document any findings

### 6.6 `src/llm/inference_router.py` - Use config service
- [ ] 6.6.1 Remove import of `DEFAULT_FREE_TIER_MODEL, enforce_free_tier` (line 16)
- [ ] 6.6.2 Add import of `ModelConfigService`
- [ ] 6.6.3 Replace `config.get_llm_model()` with `ModelConfigService.get_active_model("inference")` (line 196)
- [ ] 6.6.4 Replace `config.INFERENCE_DEFAULT_MODEL` with config service call (line 243)
- [ ] 6.6.5 Replace `_enforce_free_tier()` with `ModelConfigService.validate_model()` (lines 361-371)

### 6.7 `src/services/ingestion_pipeline.py` - Use config service
- [ ] 6.7.1 Replace `config.EMBEDDING_MODEL` with `ModelConfigService.get_active_model("embedding")` (line 321)
- [ ] 6.7.2 Replace `config.EMBEDDING_MODEL` in metadata (line 354)

### 6.8 `src/services/lineage_inference.py` - Use config service
- [ ] 6.8.1 Replace `config.EMBEDDING_MODEL` with `ModelConfigService.get_active_model("embedding")` (line 136)

### 6.9 `src/services/knowledge_inference.py` - Use config service
- [ ] 6.9.1 Replace `config.EMBEDDING_MODEL` with `ModelConfigService.get_active_model("embedding")` (line 361)

### 6.10 `src/api/main_local.py` - Use config service and auto-seed
- [ ] 6.10.1 Replace `config.LLM_MODEL, config.EMBEDDING_MODEL` with config service (line 205)
- [ ] 6.10.2 Replace all `config.EMBEDDING_MODEL` references (lines 231, 253, 268, 350)
- [ ] 6.10.3 Add startup initialization in `app.startup_event()` or `lifespan()` context
- [ ] 6.10.4 On startup, call `ModelConfigService._auto_seed_if_empty()` to populate defaults if table is empty
- [ ] 6.10.5 Verify all required usage_types have at least one enabled config after auto-seed
- [ ] 6.10.6 Log migration status: "Model configuration auto-seeded" or "Model configuration already initialized"
- [ ] 6.10.7 If any required usage_type has no enabled config, log ERROR but do not crash (graceful degradation)

### 6.11 `src/utils/exporters.py` - Use config service
- [ ] 6.11.1 Replace hardcoded `"nomic-embed-text"` with `ModelConfigService.get_active_model("embedding")` (line 271)

### 6.12 Update `src/llm/free_tier.py` - Mark as deprecated
- [ ] 6.12.1 Add module-level deprecation warning at top of file
- [ ] 6.12.2 Add comment: "This module is deprecated as of [version]. Use ModelConfigService instead."
- [ ] 6.12.3 Do NOT delete yet - may be imported by third-party code or migrations

## 7. Fallback Chain Implementation
- [ ] 7.1 Implement `get_fallback_chain(usage_type)` in ModelConfigService - returns ordered list of enabled models by priority
- [ ] 7.2 In `chat_service.py` `_call_with_fallback()`: Use fallback chain from ModelConfigService instead of fixed list
- [ ] 7.3 If no enabled configs exist for usage_type, raise ValueError with message "No models configured for {usage_type}"
- [ ] 7.4 At API boundary (5.X endpoints), catch ValueError and return 503 status with error message
- [ ] 7.5 Log which model was used (primary vs fallback) in response metadata (existing chat_service logic applies)
- [ ] 7.6 Add metric: track fallback usage rate (primary vs secondary vs tertiary model selection)

## 8. Pydantic Schemas
- [ ] 8.1 Create `UsageType` enum: chat_deep, chat_semantic, chat_text, chat_graph, chat_title, embedding, inference, kg_edge_creation
- [ ] 8.2 Create `Provider` enum: openrouter, ollama
- [ ] 8.3 Create `OpenRouterModel` schema: id, name, description, context_length, supports_streaming, supports_reasoning
- [ ] 8.4 Create `OllamaModel` schema: name, size, quantization, modified_at
- [ ] 8.5 Create `ModelParameters` schema: streaming, reasoning_mode, max_tokens, temperature
- [ ] 8.6 Create `ModelConfig` schema: id, usage_type, priority, model_id, model_name, provider, parameters, enabled, timestamps
- [ ] 8.7 Create `ModelConfigRequest` schema for POST validation
- [ ] 8.8 Create `ModelConfigResponse` schema for API responses
- [ ] 8.9 Create `SeedDefaultsRequest` schema (empty or with optional override flag)

## 9. Default Configuration Values
- [ ] 9.1 Define default configs for chat_deep: deepseek/deepseek-r1-0528:free (pri 1), mistralai/devstral-2512:free (pri 2), google/gemini-2.0-flash-exp:free (pri 3)
- [ ] 9.2 Define default configs for chat_semantic: google/gemini-2.0-flash-exp:free (pri 1), qwen/qwen3-4b:free (pri 2), mistralai/mistral-7b-instruct:free (pri 3)
- [ ] 9.3 Define default configs for chat_text: google/gemini-2.0-flash-exp:free (pri 1), mistralai/mistral-7b-instruct:free (pri 2), qwen/qwen3-4b:free (pri 3)
- [ ] 9.4 Define default configs for chat_graph: mistralai/devstral-2512:free (pri 1), deepseek/deepseek-r1-0528:free (pri 2), google/gemini-2.0-flash-exp:free (pri 3)
- [ ] 9.5 Define default configs for chat_title: google/gemini-2.0-flash-exp:free (pri 1), mistralai/mistral-7b-instruct:free (pri 2), qwen/qwen3-4b:free (pri 3)
- [ ] 9.6 Define default config for embedding: nomic-embed-text (Ollama, pri 1)
- [ ] 9.7 Define default config for inference: llama3.1:8b (Ollama, pri 1)
- [ ] 9.8 Define default config for kg_edge_creation: mistralai/devstral-2512:free (pri 1), google/gemini-2.0-flash-exp:free (pri 2)

## 10. Testing
- [ ] 10.1 Write unit tests for `ModelConfigRepository` CRUD operations
- [ ] 10.2 Write unit tests for `ModelConfigService` validation and fallback logic
- [ ] 10.3 Write integration tests for `/api/v1/models/*` endpoints
- [ ] 10.4 Write mock tests for OpenRouter API integration with error scenarios
- [ ] 10.5 Write mock tests for Ollama API integration with error scenarios
- [ ] 10.6 Test chat endpoints with dynamic model configuration
- [ ] 10.7 Test embedding service with dynamic model configuration
- [ ] 10.8 Test error handling when no models configured (empty table, all disabled)
- [ ] 10.9 Test auto-seeding on first startup (empty table detection)
- [ ] 10.10 Test seed endpoint idempotency (call twice, verify no duplicates)
- [ ] 10.11 Test fallback chain logic (verify models are tried in priority order)
- [ ] 10.12 Test OpenRouter API failure graceful degradation (empty list, cached, warning logged)
- [ ] 10.13 Test Ollama API failure graceful degradation (empty list, warning logged)

## 11. Rollback & Disaster Recovery Procedures
- [ ] 11.1 Document DuckDB migration rollback steps (use existing snapshot mechanism)
- [ ] 11.2 Document procedure if seed endpoint fails (how to recover, re-run seed)
- [ ] 11.3 Document: seed endpoint is idempotent (safe to call multiple times)
- [ ] 11.4 Document: what happens if migration fails (service continues with old schema)
- [ ] 11.5 Add transaction handling: seed operation should be atomic (all-or-nothing)
- [ ] 11.6 Test rollback procedure: create test scenario and verify recovery

## 12. Documentation
- [ ] 12.1 Add OpenAPI descriptions to all new endpoints
- [ ] 12.2 Document usage_type values and their purposes
- [ ] 12.3 Document default configuration values and fallback chains
- [ ] 12.4 Document frontend integration workflow (seed → configure → use)
- [ ] 12.5 Document auto-seeding behavior on startup (when it occurs, why)
- [ ] 12.6 Document error handling: what happens when models are unavailable
- [ ] 12.7 Document API error codes: 503 when no configs exist, 400 for invalid config
- [ ] 12.8 Document temperature management: explain why per-endpoint vs per-model
- [ ] 12.9 Create migration guide: "Moving from hardcoded to configuration-driven models"
- [ ] 12.10 Add observability guide: metrics and logs to monitor for troubleshooting
