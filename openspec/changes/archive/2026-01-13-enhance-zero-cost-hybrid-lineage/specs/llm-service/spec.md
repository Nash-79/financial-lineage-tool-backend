# llm-service Spec Deltas

## ADDED Requirements

### Requirement: OpenRouterService for Zero-Cost Inference
The system SHALL provide a dedicated service for routing lineage inference requests to free-tier OpenRouter models with strict cost controls.

#### Scenario: OpenRouterService initialization
- **WHEN** system initializes `OpenRouterService`
- **THEN** it requires `OPENROUTER_API_KEY` from environment
- **AND** initializes httpx async client for HTTP calls
- **AND** loads `FREE_TIER_MODELS` whitelist
- **AND** sets default model to `google/gemini-2.0-flash-exp:free`

#### Scenario: Predict lineage method
- **WHEN** `predict_lineage(code_snippet, context_nodes)` is called
- **THEN** service constructs a structured prompt with code and context
- **AND** makes POST request to OpenRouter `/api/v1/chat/completions`
- **AND** uses `response_format={"type": "json_object"}` for strict JSON mode
- **AND** parses response into list of `LineageEdgeProposal` objects
- **AND** validates proposals before returning

#### Scenario: JSON-only response mode
- **WHEN** OpenRouter is called with strict JSON mode
- **THEN** request header includes `"response_format": {"type": "json_object"}`
- **AND** system prompt explicitly requires JSON-only output
- **AND** any non-JSON response is caught and logged as error
- **AND** empty list is returned on parsing failure (fail-open)

#### Scenario: Routing guard enforcement
- **WHEN** user specifies a model for lineage inference
- **THEN** `OpenRouterService` validates model against `FREE_TIER_MODELS`
- **AND** if model is not in whitelist, downgrades to default free model
- **AND** logs warning with original model and downgrade reason
- **AND** proceeds with free-tier model

#### Scenario: Rate limit handling
- **WHEN** OpenRouter returns 429 (Rate Limit Exceeded)
- **THEN** service catches the error and logs it
- **AND** returns empty list (fail-open, no crash)
- **AND** circuit breaker may open to prevent further requests
- **AND** system continues using deterministic lineage only

#### Scenario: Service unavailable handling
- **WHEN** OpenRouter returns 503 (Service Unavailable)
- **THEN** service catches the error and logs it
- **AND** returns empty list (fail-open)
- **AND** deterministic lineage parsing continues unaffected

#### Scenario: Lineage proposal structure
- **WHEN** OpenRouter returns proposals
- **THEN** each proposal conforms to `LineageEdgeProposal` schema:
  ```python
  {
    "source_node": "str",           # Source entity identifier
    "target_node": "str",           # Target entity identifier
    "relationship_type": "READS|WRITES",  # Relationship type
    "confidence": 0.85,             # Float 0.0-1.0
    "reasoning": "str"              # Brief explanation
  }
  ```

### Requirement: Knowledge Graph Enrichment Agent
The system SHALL provide a KG agent that proposes new edges using free-tier OpenRouter Devstral and writes them directly to Neo4j.

#### Scenario: KG agent model selection
- **WHEN** KG enrichment runs
- **THEN** it uses `mistralai/devstral-2512:free` as the default model
- **AND** requests are validated against `FREE_TIER_MODELS`

#### Scenario: KG agent edge write
- **WHEN** KG agent proposes edges
- **THEN** it writes edges directly to Neo4j
- **AND** each edge includes metadata: `source="llm"`, `model`, `confidence`, `status`
- **AND** writes are associated with the current ingestion context (project_id, file_path)

#### Scenario: KG agent logging
- **WHEN** KG agent completes
- **THEN** ingestion logs include:
  - proposed edge count
  - accepted edge count
  - model name
  - confidence summary

### Requirement: Free-Tier Model Enforcement
The system SHALL enforce zero-cost inference by restricting cloud LLM requests to free-tier models only.

#### Scenario: Free-tier model requested
- **WHEN** user or system requests generation with a free-tier model (e.g., `google/gemini-2.0-flash-exp:free`)
- **THEN** the request proceeds without modification
- **AND** the specified model is used for inference

#### Scenario: Non-free model requested
- **WHEN** a non-free model is requested (e.g., `gpt-4`, `claude-3-opus`)
- **THEN** the system SHALL automatically downgrade to `google/gemini-2.0-flash-exp:free`
- **AND** it logs a warning with the original model name and downgrade reason
- **AND** the response completes successfully with the fallback model

#### Scenario: Free-tier model whitelist
- **WHEN** system initializes
- **THEN** it SHALL define a whitelist of approved free-tier models
- **AND** whitelist includes at minimum:
  - `google/gemini-2.0-flash-exp:free`
  - `mistralai/mistral-7b-instruct:free`
  - `mistralai/devstral-2512:free` (specialized for code analysis/generation)
  - `meta-llama/llama-3.1-8b-instruct:free`
  - `deepseek/deepseek-r1:free`

### Requirement: LLM Routing and Fallback
The system SHALL route LLM requests to local Ollama by default, with automatic fallback to free-tier cloud providers when needed.

#### Scenario: Free-tier model enforcement
- **WHEN** user or system requests a specific cloud model
- **THEN** the router validates model against `FREE_TIER_MODELS` whitelist
- **AND** if model is not free-tier, it downgrades to `google/gemini-2.0-flash-exp:free`
- **AND** it logs a warning with original and replacement model names
- **AND** it returns completion using the free-tier model

#### Scenario: Cost tracking
- **WHEN** a non-free model is requested
- **THEN** system logs the event with request metadata
- **AND** metrics counter is incremented for monitoring
- **AND** user receives response with header indicating model downgrade

#### Scenario: Ollama connectivity check
- **WHEN** system starts
- **THEN** it connects to Ollama at host.docker.internal:11434
- **AND** it validates Ollama is accessible from Docker container
- **AND** it fails fast with clear error if Ollama is not running

#### Scenario: LLM completion request
- **WHEN** system needs LLM completion
- **THEN** it calls Ollama API on host machine
- **AND** it uses llama3.1:8b model
- **AND** it receives completion within 10 seconds
- **AND** it handles connection errors gracefully

## 7. Frontend Integration (For Reference)
**Note**: Frontend changes are tracked in separate repository. Document requirements here for coordination.

- [ ] 7.1 Frontend: Add dialect dropdown to file upload UI
- [ ] 7.2 Frontend: Add dialect dropdown to GitHub ingestion settings
- [ ] 7.3 Frontend: Query `/api/v1/config/sql-dialects` on mount
- [ ] 7.4 Frontend: Persist selected dialect in Zustand store
- [ ] 7.5 Frontend: Send `sql_dialect` field in ingestion API calls
