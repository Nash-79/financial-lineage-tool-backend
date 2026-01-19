## ADDED Requirements

### Requirement: Unified Model Configuration Storage
The system SHALL store ALL model configurations in DuckDB, with frontend as the single source of truth for configuration management.

#### Scenario: Model configs table schema
- **WHEN** database is initialized
- **THEN** system creates `model_configs` table with schema:
  ```sql
  CREATE TABLE IF NOT EXISTS model_configs (
    id VARCHAR PRIMARY KEY DEFAULT (uuid()),
    usage_type VARCHAR NOT NULL,        -- See UsageType enum
    priority INTEGER NOT NULL,          -- 1=primary, 2=secondary, 3=tertiary
    model_id VARCHAR NOT NULL,          -- Model identifier (OpenRouter or Ollama)
    model_name VARCHAR NOT NULL,        -- Human-readable name
    provider VARCHAR NOT NULL,          -- 'openrouter' or 'ollama'
    parameters JSON,                    -- {streaming, reasoning_mode, max_tokens, temperature}
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(usage_type, priority)
  );
  ```
- **AND** unique constraint prevents duplicate (usage_type, priority) combinations

#### Scenario: Usage type enumeration
- **WHEN** model configuration is created or validated
- **THEN** usage_type MUST be one of:
  - `chat_deep` - Deep reasoning chat endpoint
  - `chat_semantic` - Fast semantic search chat
  - `chat_text` - General text chat (no RAG)
  - `chat_graph` - Graph-focused lineage chat
  - `chat_title` - Session title generation
  - `embedding` - Vector embeddings for RAG (Ollama)
  - `inference` - General inference tasks
  - `kg_edge_creation` - Knowledge graph edge proposals
- **AND** invalid usage_type returns 400 Bad Request

#### Scenario: Provider enumeration
- **WHEN** model configuration specifies a provider
- **THEN** provider MUST be one of:
  - `openrouter` - OpenRouter API models
  - `ollama` - Local Ollama models
- **AND** provider determines which API is called for inference

### Requirement: OpenRouter Free Model Discovery
The system SHALL provide an API to discover available free-tier models from OpenRouter.

#### Scenario: Fetch free models from OpenRouter
- **WHEN** client calls `GET /api/v1/models/openrouter/free`
- **THEN** system calls OpenRouter `/api/v1/models` endpoint with `Authorization: Bearer {OPENROUTER_API_KEY}`
- **AND** filters models where `pricing.prompt == "0"` AND `pricing.completion == "0"`
- **AND** returns list of models with: id, name, description, context_length, supports_streaming, supports_reasoning
- **AND** response is cached in Redis for 1 hour

#### Scenario: OpenRouter API unavailable
- **WHEN** OpenRouter API returns error or times out
- **THEN** system returns cached model list if available with `cached: true`
- **AND** if no cache exists, returns 503 with error message

#### Scenario: Free model metadata extraction
- **WHEN** OpenRouter returns model data
- **THEN** system extracts for each free model:
  - `id`: Full model identifier (e.g., "google/gemini-2.0-flash-exp:free")
  - `name`: Human-readable name
  - `description`: Model description
  - `context_length`: Maximum context window in tokens
  - `supports_streaming`: Boolean from model capabilities
  - `supports_reasoning`: Boolean indicating chain-of-thought support

### Requirement: Ollama Model Discovery
The system SHALL provide an API to discover available local Ollama models.

#### Scenario: Fetch Ollama models
- **WHEN** client calls `GET /api/v1/models/ollama`
- **THEN** system calls Ollama `/api/tags` endpoint
- **AND** returns list of models with: name, size, quantization, modified_at
- **AND** includes model capabilities where available

#### Scenario: Ollama unavailable
- **WHEN** Ollama API is not accessible
- **THEN** system returns 503 with error message "Ollama is not running"
- **AND** includes troubleshooting hint to start Ollama

### Requirement: Frontend-Driven Configuration Seeding
The system SHALL support seeding default configurations via API call from frontend.

#### Scenario: Seed default configurations
- **WHEN** client calls `POST /api/v1/models/config/seed`
- **THEN** system checks if model_configs table is empty
- **AND** if empty, inserts default configurations for all usage_types
- **AND** returns 200 with count of configurations created
- **AND** if not empty, returns 409 Conflict with message "Configurations already exist. Use reset endpoint to replace."

#### Scenario: Reset to defaults
- **WHEN** client calls `POST /api/v1/models/config/seed` with `{"force": true}`
- **THEN** system deletes all existing configurations
- **AND** inserts default configurations for all usage_types
- **AND** returns 200 with count of configurations created

#### Scenario: Default configuration values
- **WHEN** seed operation runs
- **THEN** system creates these defaults:
  - chat_deep: deepseek/deepseek-r1-0528:free (pri 1, temp=0.6), mistralai/devstral-2512:free (pri 2), google/gemini-2.0-flash-exp:free (pri 3)
  - chat_semantic: google/gemini-2.0-flash-exp:free (pri 1, temp=0.2), qwen/qwen3-4b:free (pri 2), mistralai/mistral-7b-instruct:free (pri 3)
  - chat_text: google/gemini-2.0-flash-exp:free (pri 1, temp=0.3), mistralai/mistral-7b-instruct:free (pri 2), qwen/qwen3-4b:free (pri 3)
  - chat_graph: mistralai/devstral-2512:free (pri 1, temp=0.1), deepseek/deepseek-r1-0528:free (pri 2), google/gemini-2.0-flash-exp:free (pri 3)
  - chat_title: google/gemini-2.0-flash-exp:free (pri 1, temp=0.2), mistralai/mistral-7b-instruct:free (pri 2), qwen/qwen3-4b:free (pri 3)
  - embedding: nomic-embed-text (Ollama, pri 1)
  - inference: llama3.1:8b (Ollama, pri 1)
  - kg_edge_creation: mistralai/devstral-2512:free (pri 1), google/gemini-2.0-flash-exp:free (pri 2)

### Requirement: Configuration-Driven Model Selection
The system SHALL read model assignments from model_configs table at runtime with no hardcoded fallbacks.

#### Scenario: Get active model for usage type
- **WHEN** backend service needs a model for a specific usage_type
- **THEN** it calls `ModelConfigService.get_active_model(usage_type)`
- **AND** service queries model_configs for that usage_type, ordered by priority, filtered by enabled=true
- **AND** returns the first (priority=1) enabled model configuration

#### Scenario: No configuration exists
- **WHEN** backend service requests model for usage_type with no configurations
- **THEN** system returns 503 Service Unavailable
- **AND** response body includes: `{"error": "No models configured", "usage_type": "{usage_type}", "action": "Configure models via frontend"}`
- **AND** system does NOT fall back to hardcoded values

#### Scenario: All models disabled
- **WHEN** all configurations for a usage_type have enabled=false
- **THEN** system returns 503 Service Unavailable
- **AND** response body includes: `{"error": "All models disabled", "usage_type": "{usage_type}", "action": "Enable at least one model via frontend"}`

### Requirement: Fallback Chain from Configuration
The system SHALL build fallback chains from enabled configurations ordered by priority.

#### Scenario: Build fallback chain
- **WHEN** system needs fallback chain for a usage_type
- **THEN** it queries model_configs WHERE usage_type = ? AND enabled = true ORDER BY priority
- **AND** returns list of model configurations in priority order
- **AND** LLM gateway iterates through chain on errors (429, 503, timeout, parse failure)

#### Scenario: Fallback execution
- **WHEN** primary model (priority=1) fails
- **THEN** system tries next enabled model in chain (priority=2)
- **AND** logs fallback event with: from_model, to_model, reason, usage_type
- **AND** if all models in chain fail, returns 503 with exhaustion details

#### Scenario: Log model usage
- **WHEN** LLM request completes successfully
- **THEN** response metadata includes: `{"model_used": "{model_id}", "priority": 1, "fallback_count": 0}`
- **AND** if fallback occurred: `{"model_used": "{model_id}", "priority": 2, "fallback_count": 1, "primary_error": "Rate limit exceeded"}`

### Requirement: Model Parameters Application
The system SHALL apply configured parameters to LLM requests.

#### Scenario: Parameters JSON structure
- **WHEN** model configuration is stored or retrieved
- **THEN** parameters field contains:
  ```json
  {
    "streaming": true,           // Enable SSE streaming
    "reasoning_mode": false,     // Enable chain-of-thought (DeepSeek R1)
    "max_tokens": 4096,          // Maximum response tokens
    "temperature": 0.3           // Sampling temperature (0.0-2.0)
  }
  ```
- **AND** all fields are optional with defaults: streaming=true, reasoning_mode=false, max_tokens=4096, temperature=0.3

#### Scenario: Apply parameters to OpenRouter request
- **WHEN** chat endpoint makes OpenRouter request
- **THEN** it reads parameters from the selected model configuration
- **AND** passes temperature, max_tokens to request body
- **AND** if reasoning_mode=false, includes `response_format={"type": "json_object"}`
- **AND** if reasoning_mode=true, omits JSON constraint to allow thinking tokens

#### Scenario: Apply parameters to Ollama request
- **WHEN** embedding or inference service makes Ollama request
- **THEN** it reads model_id from configuration
- **AND** passes temperature, max_tokens where applicable
- **AND** uses configured model instead of hardcoded value

## REMOVED Requirements

### Requirement: Hardcoded FREE_TIER_MODELS whitelist
**Reason**: Replaced by dynamic configuration from frontend. Free models are discovered via OpenRouter API.
**Migration**: Frontend fetches available models via `GET /api/v1/models/openrouter/free` and configures them via `POST /api/v1/models/config`.

### Requirement: Hardcoded model assignments in chat routing
**Reason**: All model assignments now come from model_configs table.
**Migration**: Frontend calls `POST /api/v1/models/config/seed` to initialize defaults, then manages via configuration API.

## MODIFIED Requirements

### Requirement: CQRS-based chat endpoint routing with intent-optimized models
The system SHALL route chat requests using configurations from model_configs table.

#### Scenario: Chat routing from configuration
- **WHEN** chat endpoint (deep, semantic, text, graph, title) receives request
- **THEN** it calls `ModelConfigService.get_fallback_chain(usage_type)`
- **AND** usage_type is derived from endpoint: `/api/chat/deep` → `chat_deep`, etc.
- **AND** uses returned fallback chain for model selection
- **AND** applies parameters from configuration to LLM request

#### Scenario: No hardcoded defaults
- **WHEN** system routes chat requests
- **THEN** it does NOT use any hardcoded model values
- **AND** if no configuration exists, returns 503 with configuration instructions
- **AND** frontend is responsible for ensuring configurations exist

### Requirement: Embedding Generation
The system SHALL read embedding model from configuration.

#### Scenario: Embedding model from config
- **WHEN** system needs to generate embeddings
- **THEN** it calls `ModelConfigService.get_active_model("embedding")`
- **AND** uses configured model_id for Ollama embedding request
- **AND** if no configuration, returns 503 with message "Embedding model not configured"

### Requirement: Knowledge Graph Enrichment Agent
The system SHALL read KG edge creation model from configuration.

#### Scenario: KG agent model from config
- **WHEN** KG enrichment runs
- **THEN** it calls `ModelConfigService.get_fallback_chain("kg_edge_creation")`
- **AND** uses configured models for edge proposal generation
- **AND** if no configuration, returns 503 with message "KG edge creation model not configured"
