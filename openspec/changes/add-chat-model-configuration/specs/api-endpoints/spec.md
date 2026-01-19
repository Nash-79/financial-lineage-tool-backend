## ADDED Requirements

### Requirement: OpenRouter Model Discovery API
The system SHALL provide an endpoint to discover available free-tier OpenRouter models.

#### Scenario: List free OpenRouter models
- **WHEN** client calls `GET /api/v1/models/openrouter/free`
- **THEN** system returns 200 with JSON body:
  ```json
  {
    "models": [
      {
        "id": "google/gemini-2.0-flash-exp:free",
        "name": "Gemini 2.0 Flash Experimental",
        "description": "Fast, free experimental model from Google",
        "context_length": 1000000,
        "supports_streaming": true,
        "supports_reasoning": false
      },
      {
        "id": "deepseek/deepseek-r1-0528:free",
        "name": "DeepSeek R1",
        "description": "Reasoning-focused model with chain-of-thought",
        "context_length": 65536,
        "supports_streaming": true,
        "supports_reasoning": true
      }
    ],
    "cached": false,
    "fetched_at": "2026-01-17T10:30:00Z"
  }
  ```
- **AND** `cached` indicates whether response came from Redis cache
- **AND** `fetched_at` shows when data was retrieved from OpenRouter

#### Scenario: OpenRouter API failure
- **WHEN** OpenRouter API is unavailable
- **THEN** system returns cached data with `cached: true` if available
- **AND** if no cache exists, returns 503 Service Unavailable

### Requirement: Ollama Model Discovery API
The system SHALL provide an endpoint to discover available local Ollama models.

#### Scenario: List Ollama models
- **WHEN** client calls `GET /api/v1/models/ollama`
- **THEN** system returns 200 with JSON body:
  ```json
  {
    "models": [
      {
        "name": "llama3.1:8b",
        "size": 4700000000,
        "quantization": "Q4_0",
        "modified_at": "2026-01-15T08:00:00Z"
      },
      {
        "name": "nomic-embed-text",
        "size": 274000000,
        "quantization": null,
        "modified_at": "2026-01-10T12:00:00Z"
      }
    ],
    "ollama_version": "0.1.27"
  }
  ```

#### Scenario: Ollama unavailable
- **WHEN** Ollama is not running
- **THEN** system returns 503 Service Unavailable:
  ```json
  {
    "error": "Ollama is not running",
    "detail": "Unable to connect to Ollama at localhost:11434",
    "hint": "Start Ollama with: ollama serve"
  }
  ```

### Requirement: Model Configuration CRUD API
The system SHALL provide endpoints for frontend to manage ALL model configurations.

#### Scenario: Get all model configurations
- **WHEN** client calls `GET /api/v1/models/config`
- **THEN** system returns 200 with JSON body:
  ```json
  {
    "configs": {
      "chat_deep": [
        {
          "id": "uuid-1",
          "usage_type": "chat_deep",
          "priority": 1,
          "model_id": "deepseek/deepseek-r1-0528:free",
          "model_name": "DeepSeek R1",
          "provider": "openrouter",
          "parameters": {
            "streaming": true,
            "reasoning_mode": true,
            "max_tokens": 4096,
            "temperature": 0.6
          },
          "enabled": true,
          "created_at": "2026-01-17T10:00:00Z",
          "updated_at": "2026-01-17T10:00:00Z"
        }
      ],
      "chat_semantic": [...],
      "chat_text": [...],
      "chat_graph": [...],
      "chat_title": [...],
      "embedding": [...],
      "inference": [...],
      "kg_edge_creation": [...]
    }
  }
  ```
- **AND** configurations are ordered by priority within each usage_type

#### Scenario: Upsert model configuration
- **WHEN** client calls `POST /api/v1/models/config` with valid body
- **THEN** system validates and upserts (insert or update on conflict)
- **AND** returns 200 with the created/updated configuration
- **AND** `updated_at` timestamp is refreshed

#### Scenario: Upsert validation failure
- **WHEN** client calls `POST /api/v1/models/config` with invalid data
- **THEN** system returns 400 Bad Request:
  ```json
  {
    "error": "Validation failed",
    "details": [
      {"field": "usage_type", "message": "Must be one of: chat_deep, chat_semantic, chat_text, chat_graph, chat_title, embedding, inference, kg_edge_creation"},
      {"field": "priority", "message": "Must be 1, 2, or 3"}
    ]
  }
  ```

#### Scenario: Delete model configuration
- **WHEN** client calls `DELETE /api/v1/models/config/{usage_type}/{priority}`
- **THEN** system deletes the matching configuration
- **AND** returns 204 No Content on success

#### Scenario: Delete non-existent configuration
- **WHEN** client calls DELETE for missing config
- **THEN** system returns 404 Not Found

### Requirement: Configuration Seeding API
The system SHALL provide an endpoint for frontend to seed default configurations.

#### Scenario: Seed defaults (first time)
- **WHEN** client calls `POST /api/v1/models/config/seed` with empty body or `{"force": false}`
- **AND** model_configs table is empty
- **THEN** system inserts all default configurations
- **AND** returns 200:
  ```json
  {
    "status": "seeded",
    "configurations_created": 24,
    "message": "Default configurations have been created"
  }
  ```

#### Scenario: Seed when configs exist
- **WHEN** client calls `POST /api/v1/models/config/seed` with `{"force": false}`
- **AND** model_configs table has existing data
- **THEN** system returns 409 Conflict:
  ```json
  {
    "error": "Configurations already exist",
    "detail": "Use force=true to reset to defaults",
    "existing_count": 24
  }
  ```

#### Scenario: Force reset to defaults
- **WHEN** client calls `POST /api/v1/models/config/seed` with `{"force": true}`
- **THEN** system deletes all existing configurations
- **AND** inserts all default configurations
- **AND** returns 200:
  ```json
  {
    "status": "reset",
    "configurations_deleted": 24,
    "configurations_created": 24,
    "message": "Configurations have been reset to defaults"
  }
  ```

### Requirement: Model Configuration Request Schema
The system SHALL validate model configuration requests against a strict schema.

#### Scenario: Valid configuration request
- **WHEN** client submits model configuration
- **THEN** request body must match schema:
  ```json
  {
    "usage_type": "chat_deep",          // Required: see UsageType enum
    "priority": 1,                      // Required: 1, 2, or 3
    "model_id": "string",               // Required: Model identifier
    "model_name": "string",             // Required: Human-readable name
    "provider": "openrouter",           // Required: openrouter | ollama
    "parameters": {                     // Optional: defaults applied if omitted
      "streaming": true,                // Optional: default true
      "reasoning_mode": false,          // Optional: default false
      "max_tokens": 4096,               // Optional: default 4096
      "temperature": 0.3                // Optional: default 0.3
    },
    "enabled": true                     // Optional: default true
  }
  ```

#### Scenario: Usage type validation
- **WHEN** usage_type is provided
- **THEN** it MUST be one of:
  - `chat_deep`
  - `chat_semantic`
  - `chat_text`
  - `chat_graph`
  - `chat_title`
  - `embedding`
  - `inference`
  - `kg_edge_creation`
- **AND** invalid value returns 400 with field-level error

#### Scenario: Provider validation
- **WHEN** provider is provided
- **THEN** it MUST be one of: `openrouter`, `ollama`
- **AND** invalid value returns 400 with field-level error

#### Scenario: Parameter range validation
- **WHEN** parameters are provided
- **THEN** system validates:
  - `temperature` must be >= 0.0 and <= 2.0
  - `max_tokens` must be > 0 and <= 128000
  - `streaming` must be boolean
  - `reasoning_mode` must be boolean
