## ADDED Requirements
### Requirement: Document indexing with LlamaIndex
The system SHALL index code chunks using LlamaIndex for all ingestion entry points.

#### Scenario: Index files from all ingestion sources
- **WHEN** a file is ingested via `/api/v1/ingest`, `/api/v1/files/upload`, or `/api/v1/github/ingest`
- **THEN** the system chunks the file using the semantic chunker (sql, python, or generic)
- **AND** it converts chunks to LlamaIndex Document objects
- **AND** it generates embeddings via Ollama
- **AND** it stores embeddings in Qdrant via VectorStoreIndex
- **AND** metadata is preserved (file_path, relative_path, chunk_type, tables, columns, source, project_id, repository_id)

### Requirement: Chat endpoints SHALL NOT use LlamaIndex for generation
The system SHALL use direct retrieval (Qdrant + Neo4j) with OpenRouter free-tier models for all `/api/chat/*` endpoints, without LlamaIndex abstractions.

#### Scenario: Chat endpoint routing without LlamaIndex
- **WHEN** any `/api/chat/*` endpoint receives a request
- **THEN** it retrieves context directly from Qdrant vector store and/or Neo4j graph store
- **AND** it constructs prompts manually using endpoint-specific system prompts
- **AND** it calls OpenRouter free-tier models for generation (never LlamaIndex query engine)
- **AND** it parses LLM output into structured internal format (`answer`, `evidence`, `next_actions`, `warnings`)
- **AND** it transforms internal format to `ChatResponse` API schema for return
- **AND** it populates the `model` field at root level with the actual model used (e.g., `"deepseek/deepseek-r1:free"`)
- **AND** if fallback occurred, the `model` field reflects the successful fallback model, not the original failed model

#### Scenario: Embeddings still use Ollama
- **WHEN** chat endpoints need to embed user queries
- **THEN** they use local Ollama for embedding generation
- **AND** embeddings are used for Qdrant vector similarity search
- **AND** OpenRouter is only used for text generation, not embeddings

### Requirement: Base system prompt for all chat endpoints
The system SHALL use a shared base system prompt that enforces evidence-based responses and structured JSON output.

#### Scenario: Base prompt applied to all endpoints
- **WHEN** any `/api/chat/*` endpoint constructs an LLM request
- **THEN** it includes the base system prompt:
  ```
  You are the Financial Lineage Tool assistant. Your job is to answer questions about data lineage, dependencies, transformations, and repository artifacts using ONLY the evidence provided in the request context (vector snippets, graph results, and metadata). Do not invent tables, columns, files, edges, or SQL logic.

  Rules:
  - Treat Neo4j/graph evidence as authoritative for lineage claims (upstream/downstream, DERIVES/READS_FROM, dependency edges).
  - Treat vector snippets as supporting evidence (code or docs excerpts). If evidence is missing or ambiguous, say so and propose what to search next.
  - Prefer precise, testable statements (file path, object name, query/view name, edge/path, confidence if provided).
  - Never mention internal implementation details (no "I used Qdrant/Neo4j" unless asked). Just cite evidence identifiers passed in.
  - Never output hidden reasoning. Provide final conclusions only.

  Output format:
  Return a single JSON object with:
  {
    "answer": string,                  // concise, directly addresses the user
    "evidence": [                      // 0..N items
      { "type": "graph|chunk|doc", "id": string, "note": string }
    ],
    "next_actions": [string],          // 0..N suggested follow-ups (queries to run, entities to inspect)
    "warnings": [string]               // 0..N (missing evidence, conflicts, assumptions)
  }

  If the user asks for code changes, respond with steps and minimal patches, grounded in evidence.
  ```
- **AND** endpoint-specific additions are appended to this base prompt

#### Scenario: JSON-only output enforcement with safe fallback
- **WHEN** LLM response is received (except streaming endpoints)
- **THEN** the system attempts to parse it as JSON
- **AND** validates it has `answer`, `evidence`, `next_actions`, and `warnings` keys
- **AND** if parsing fails or keys are missing, logs full response with model name and endpoint
- **AND** returns safe fallback response with warnings array indicating malformed LLM output
- **AND** increments `chat_malformed_response_count` metric for monitoring

### Requirement: /api/chat/deep endpoint-specific prompt
The system SHALL append deep-analysis-specific instructions to the base prompt for `/api/chat/deep` requests.

#### Scenario: Deep endpoint prompt additions
- **WHEN** `/api/chat/deep` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for DEEP:
  - Synthesize across graph evidence + multiple snippets. If they conflict, call it out and pick the most authoritative source.
  - When explaining lineage, include: (a) the key path(s), (b) the transformation boundary (view/job/model), and (c) what to verify next.
  - Keep the answer structured in paragraphs or bullets inside the "answer" string, but still emit valid JSON.
  ```
- **AND** uses primary model `deepseek/deepseek-r1:free` with fallbacks to `google/gemini-2.0-flash-exp:free`, then `meta-llama/llama-3.1-8b-instruct:free`

#### Scenario: Deep endpoint retrieves top 10 context
- **WHEN** `/api/chat/deep` retrieves context
- **THEN** it fetches top 10 relevant chunks from Qdrant
- **AND** it fetches related graph nodes and edges from Neo4j when applicable
- **AND** it includes both in the LLM prompt as structured evidence

### Requirement: /api/chat/graph endpoint-specific prompt
The system SHALL append graph-first instructions to the base prompt for `/api/chat/graph` requests.

#### Scenario: Graph endpoint prompt additions
- **WHEN** `/api/chat/graph` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for GRAPH:
  - Answer using graph evidence first. If no graph evidence supports a lineage claim, do not claim it.
  - Summarize nodes, edges, and paths clearly (entity names + relationship type). Avoid long prose.
  ```
- **AND** uses primary model `mistralai/devstral-2512:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `google/gemini-2.0-flash-exp:free`

#### Scenario: Graph endpoint prioritizes Neo4j evidence
- **WHEN** `/api/chat/graph` retrieves context
- **THEN** it queries Neo4j first for nodes, edges, and paths
- **AND** it includes vector chunks only as supplementary evidence
- **AND** the prompt explicitly marks graph evidence as authoritative

### Requirement: /api/chat/semantic endpoint-specific prompt
The system SHALL append fast-search instructions to the base prompt for `/api/chat/semantic` requests.

#### Scenario: Semantic endpoint prompt additions
- **WHEN** `/api/chat/semantic` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for SEMANTIC:
  - Focus on the most relevant snippets and return a short summary.
  - If the user asks lineage questions and no graph evidence is present, explicitly recommend calling /api/chat/deep or /api/chat/graph in next_actions.
  - Keep "answer" under ~1200 characters unless the user explicitly asked for detail.
  ```
- **AND** uses primary model `google/gemini-2.0-flash-exp:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `mistralai/mistral-7b-instruct:free`

#### Scenario: Semantic endpoint retrieves top 5 context
- **WHEN** `/api/chat/semantic` retrieves context
- **THEN** it fetches top 5 relevant chunks from Qdrant
- **AND** it skips Neo4j queries for speed
- **AND** the response is optimized for low latency

### Requirement: /api/chat/text endpoint-specific prompt
The system SHALL append no-RAG instructions to the base prompt for `/api/chat/text` requests.

#### Scenario: Text endpoint prompt additions
- **WHEN** `/api/chat/text` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for TEXT:
  - You have no retrieval context. Do not pretend you saw the repo or graph.
  - Provide general guidance, and put specific "what I would need" items into next_actions.
  ```
- **AND** uses primary model `google/gemini-2.0-flash-exp:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `mistralai/mistral-7b-instruct:free`

#### Scenario: Text endpoint skips retrieval
- **WHEN** `/api/chat/text` processes a request
- **THEN** it does NOT query Qdrant or Neo4j
- **AND** it passes only user query and base prompt to LLM
- **AND** it returns general guidance without specific evidence

### Requirement: /api/chat/title endpoint-specific prompt
The system SHALL append title-generation instructions to the base prompt for `/api/chat/title` requests.

#### Scenario: Title endpoint prompt additions
- **WHEN** `/api/chat/title` constructs LLM request
- **THEN** it appends to base prompt:
  ```
  Additional rules for TITLE:
  - Produce a short title (3–7 words) that describes the user's main intent. Output JSON with:
  { "answer": "<title>", "evidence": [], "next_actions": [], "warnings": [] }
  ```
- **AND** uses primary model `google/gemini-2.0-flash-exp:free` with fallbacks to `meta-llama/llama-3.1-8b-instruct:free`, then `mistralai/mistral-7b-instruct:free`

#### Scenario: Title endpoint returns compact response
- **WHEN** `/api/chat/title` processes a request
- **THEN** it returns JSON with `answer` containing 3-7 word title
- **AND** `evidence`, `next_actions`, and `warnings` are empty arrays
- **AND** response is returned within 2 seconds

### Requirement: Model fallback routing for chat endpoints
The system SHALL define primary/secondary/tertiary free-tier models for each chat endpoint and retry through fallbacks on errors.

#### Scenario: Primary model success
- **WHEN** chat endpoint calls primary model and it succeeds
- **THEN** the response is returned immediately
- **AND** no fallback models are tried
- **AND** the `model` field in response contains the primary model identifier (e.g., `"deepseek/deepseek-r1:free"` for `/api/chat/deep`)

#### Scenario: Primary model fails, fallback to secondary
- **WHEN** primary model returns error, rate limit (429), timeout, or parse failure
- **THEN** the system logs the error with model name, endpoint, and reason
- **AND** it retries with secondary model after exponential backoff (base_delay * backoff_factor^(retry_count-1), e.g., 2.0s for first fallback)
- **AND** it uses the same prompt and context
- **AND** increments `chat_model_fallback_count{endpoint, from_model, to_model, reason}` metric
- **AND** fallback is triggered by FAILURE only, not by slow response within timeout
- **AND** if secondary succeeds, the `model` field in response contains the secondary model identifier (e.g., `"google/gemini-2.0-flash-exp:free"`)
- **AND** the primary model failure is logged server-side but NOT exposed to the client in the response

#### Scenario: Secondary fails, fallback to tertiary
- **WHEN** secondary model also fails
- **THEN** the system logs the error with model name and reason
- **AND** it retries with tertiary model after exponential backoff (2.0s * 2.0^1 = 4.0s for second fallback, well-gapped)
- **AND** if tertiary fails, returns 503 Service Unavailable with JSON body:
  ```json
  {
    "error": "All free-tier models exhausted for this endpoint",
    "endpoint": "/api/chat/deep",
    "attempts": [
      {"model": "deepseek/deepseek-r1:free", "error": "Rate limit exceeded (429)", "timestamp": "2026-01-13T10:30:00Z"},
      {"model": "google/gemini-2.0-flash-exp:free", "error": "Timeout after 90s", "timestamp": "2026-01-13T10:32:00Z"},
      {"model": "meta-llama/llama-3.1-8b-instruct:free", "error": "Service unavailable (503)", "timestamp": "2026-01-13T10:36:00Z"}
    ],
    "retry_after": 120
  }
  ```
- **AND** increments `chat_all_models_failed{endpoint}` metric
- **AND** `retry_after` suggests client back-off (2 minutes for free-tier recovery)

#### Scenario: Model whitelist enforcement during fallback
- **WHEN** any fallback model is selected
- **THEN** the system validates it is in `FREE_TIER_MODELS` whitelist
- **AND** if not whitelisted, it downgrades to `google/gemini-2.0-flash-exp:free`
- **AND** logs warning with original model and downgrade reason

### Requirement: Free-tier model whitelist for chat endpoints
The system SHALL maintain a whitelist of approved zero-cost OpenRouter models and enforce it for all chat generation requests.

#### Scenario: Chat endpoint model whitelist
- **WHEN** system initializes chat routing
- **THEN** it defines `FREE_TIER_MODELS` whitelist containing:
  - `google/gemini-2.0-flash-exp:free`
  - `mistralai/mistral-7b-instruct:free`
  - `mistralai/devstral-2512:free`
  - `meta-llama/llama-3.1-8b-instruct:free`
  - `deepseek/deepseek-r1:free`
- **AND** only these models are allowed for chat endpoints

#### Scenario: Non-free model requested in chat
- **WHEN** a non-free model is requested (e.g., user override or misconfiguration)
- **THEN** the system downgrades to `google/gemini-2.0-flash-exp:free`
- **AND** logs warning with original model name and "not in FREE_TIER_MODELS" reason
- **AND** proceeds with free-tier model

### Requirement: CQRS-based chat endpoint routing with intent-optimized models
The system SHALL route chat requests using Command Query Responsibility Segregation (CQRS) principles, mapping user intent to retrieval strategy and model selection.

#### Scenario: CQRS routing table
- **WHEN** system initializes chat routing configuration
- **THEN** it defines intent-to-strategy mappings (time budgets are typical targets, not hard limits):
  - `/api/chat/deep`: Complex Reasoning → Hybrid Retrieval (top 10 vector + 2-hop graph) → DeepSeek R1 (reasoning/CoT) → ~30-60s typical (free-tier variable)
  - `/api/chat/graph`: Structure/Lineage Analysis → Graph Traversal (upstream/downstream paths + schema) → Devstral 2 (code/structure aware) → ~10-20s typical
  - `/api/chat/semantic`: Lookup/Search → Vector Search (top 5 chunks) → Gemini 2.0 Flash (high speed/context) → ~5-10s typical
  - `/api/chat/text`: General/Help → No RAG (direct context only) → Llama 3.1 8B (general chat) → ~3-8s typical
  - `/api/chat/title`: Session Naming → No RAG → Gemini 2.0 Flash or Llama 3.1 → ~2-5s typical
- **AND** time budgets reflect free-tier model latency variability (no SLA guarantees)
- **AND** fallbacks are triggered by errors (429, 503, timeout, parse failure), NOT by exceeding time budget

#### Scenario: Default models per endpoint with temperature settings
- **WHEN** system routes chat requests
- **THEN** it uses these default models (primary/secondary/tertiary) with temperature settings:
  - `/api/chat/deep`: `deepseek/deepseek-r1:free` (temp=0.6 for reasoning exploration) → `google/gemini-2.0-flash-exp:free` (temp=0.6) → `meta-llama/llama-3.1-8b-instruct:free` (temp=0.6)
  - `/api/chat/graph`: `mistralai/devstral-2512:free` (temp=0.1 for strict graph interpretation) → `meta-llama/llama-3.1-8b-instruct:free` (temp=0.1) → `google/gemini-2.0-flash-exp:free` (temp=0.1)
  - `/api/chat/semantic`: `google/gemini-2.0-flash-exp:free` (temp=0.2) → `meta-llama/llama-3.1-8b-instruct:free` (temp=0.2) → `mistralai/mistral-7b-instruct:free` (temp=0.2)
  - `/api/chat/text`: `meta-llama/llama-3.1-8b-instruct:free` (temp=0.3) → `google/gemini-2.0-flash-exp:free` (temp=0.3) → `mistralai/mistral-7b-instruct:free` (temp=0.3)
  - `/api/chat/title`: `google/gemini-2.0-flash-exp:free` (temp=0.2) → `meta-llama/llama-3.1-8b-instruct:free` (temp=0.2) → `mistralai/mistral-7b-instruct:free` (temp=0.2)
- **AND** these mappings are exposed via `/api/v1/config` (see api-endpoints spec)
- **AND** temperature is configurable per endpoint via environment variables or config file

#### Scenario: Hybrid retrieval for deep mode
- **WHEN** `/api/chat/deep` builds context
- **THEN** it executes hybrid retrieval:
  1. Embeds query using local Ollama
  2. Fetches top 10 relevant chunks from Qdrant vector search
  3. Extracts entity mentions from query (tables, views, functions via regex/keyword)
  4. Executes 2-hop graph traversal from extracted entities in Neo4j
  5. Serializes both vector snippets and graph paths into structured context string
- **AND** context includes evidence IDs (URNs) for all chunks and graph entities
- **AND** total context construction completes within 5 seconds

#### Scenario: Graph-first retrieval for graph mode
- **WHEN** `/api/chat/graph` builds context
- **THEN** it prioritizes Neo4j:
  1. Extracts entity mentions from query
  2. Queries Neo4j for upstream/downstream paths (up to 3 hops)
  3. Fetches node schema and edge metadata
  4. Optionally includes top 3 relevant chunks as supplementary evidence
  5. Formats graph paths as: `node1 -[RELATIONSHIP]-> node2`
- **AND** context explicitly marks graph evidence as authoritative
- **AND** graph query completes within 3 seconds

#### Scenario: Vector-only retrieval for semantic mode
- **WHEN** `/api/chat/semantic` builds context
- **THEN** it executes fast vector search:
  1. Embeds query using local Ollama
  2. Fetches top 5 relevant chunks from Qdrant
  3. Skips Neo4j queries for speed
  4. Formats chunks with URNs and text excerpts
- **AND** retrieval completes within 1 second
- **AND** if query contains lineage keywords (upstream, downstream, depends), includes warning suggesting `/api/chat/deep` or `/api/chat/graph`

### Requirement: Evidence ID format for resolution
The system SHALL format evidence identifiers using the URN scheme defined in the api-endpoints spec.

#### Scenario: Evidence URN alignment
- **WHEN** system includes evidence identifiers in chat responses
- **THEN** it uses `urn:li:{entity_type}:{project_id}:{asset_path}` as defined in `api-endpoints` requirements
- **AND** it includes `entity_type` and `asset_path` conventions from the API contract

### Requirement: DeepSeek R1 reasoning token handling
The system SHALL enforce strict JSON mode to suppress DeepSeek R1's Chain-of-Thought "thinking" tokens in chat responses.

#### Scenario: DeepSeek R1 JSON-only mode
- **WHEN** `/api/chat/deep` calls `deepseek/deepseek-r1:free`
- **THEN** it includes `response_format={"type": "json_object"}` in the API request
- **AND** this forces DeepSeek to output only valid JSON, suppressing internal reasoning tokens
- **AND** if DeepSeek still emits thinking tokens, the JSON parser will fail and trigger safe fallback

#### Scenario: Reasoning preservation in logs
- **WHEN** DeepSeek R1 generates response in debug mode
- **THEN** raw response (including any leaked reasoning tokens) is logged at DEBUG level
- **AND** only the parsed JSON is returned to client
- **AND** logs are tagged with `model=deepseek-r1, endpoint=deep`

### Requirement: Resilient LLM gateway with retry logic
The system SHALL wrap all OpenRouter calls in a resilient gateway that handles rate limits, timeouts, and model failures.

#### Scenario: Retry configuration
- **WHEN** system initializes LLM gateway
- **THEN** it loads configuration:
  - `max_retries`: 3 (primary + 2 fallbacks)
  - `backoff_factor`: 2.0 (exponential backoff multiplier for well-gapped retries)
  - `base_delay`: 2.0 seconds (initial retry delay, gives free-tier models time to recover)
  - `timeout_per_request`: 90 seconds for deep (DeepSeek R1 can be slow), 45 seconds for graph/semantic, 30 seconds for text/title
- **AND** configuration is stored in environment variables and loaded via `config.py`
- **AND** timeouts are generous to accommodate free-tier variability

#### Scenario: Rate limit (429) handling
- **WHEN** OpenRouter returns 429 (Rate Limit Exceeded)
- **THEN** system parses `Retry-After` header if present
- **AND** waits for `max(Retry-After, base_delay * backoff_factor^(retry-1))` seconds before fallback
- **AND** falls back to next model (does NOT retry same model on rate limit)
- **AND** logs rate limit with model, endpoint, retry_after value, and timestamp
- **AND** well-gapped fallback (minimum 2s, up to 4s for second fallback) gives free-tier time to recover

#### Scenario: Timeout handling
- **WHEN** OpenRouter request exceeds timeout_per_request (90s for deep, 45s for graph/semantic, 30s for text/title)
- **THEN** system cancels request and logs timeout with model, endpoint, and timeout value
- **AND** waits for backoff delay (2s for first fallback, 4s for second) before next model
- **AND** increments `chat_timeout_count{endpoint, model}` metric
- **AND** does NOT immediately retry (gives downstream systems time to recover)

#### Scenario: Service unavailable (503) handling
- **WHEN** OpenRouter returns 503 (Service Unavailable)
- **THEN** system logs error and immediately falls back to next model
- **AND** does NOT retry the same model (assume temporary outage)
- **AND** increments `chat_service_unavailable_count{endpoint, model}` metric

### Requirement: Context window management for chat endpoints
The system SHALL construct context strings that fit within model token limits while preserving evidence fidelity.

#### Scenario: Context truncation for deep mode
- **WHEN** `/api/chat/deep` builds context exceeding 8000 tokens (estimated)
- **THEN** it prioritizes graph evidence over vector chunks
- **AND** truncates vector chunks from oldest to newest
- **AND** includes warning in response: `"warnings": ["Context truncated: X chunks omitted due to token limit"]`
- **AND** logs truncation event with original and final chunk counts

#### Scenario: Context serialization format
- **WHEN** system serializes Qdrant chunks and Neo4j paths into context string
- **THEN** it uses structured format:
  ```
  ## Vector Evidence
  [urn:li:qdrant-chunk:project_id:code_chunks/abc123]
  File: src/models/transaction.py
  Type: python_class
  Content: class Transaction(BaseModel): ...

  [urn:li:qdrant-chunk:project_id:code_chunks/def456]
  File: sql/views/customer_summary.sql
  Type: sql_view
  Content: CREATE VIEW customer_summary AS SELECT ...

  ## Graph Evidence
  [urn:li:neo4j-node:project_id:Table/transactions] -[READS_FROM]-> [urn:li:neo4j-node:project_id:Table/customers]
  Path: transactions (Table) -> READS_FROM -> customers (Table)
  Confidence: 0.95
  Source: deterministic

  ## User Query
  {user_query}
  ```
- **AND** evidence IDs are preserved for LLM to include in `evidence` array

