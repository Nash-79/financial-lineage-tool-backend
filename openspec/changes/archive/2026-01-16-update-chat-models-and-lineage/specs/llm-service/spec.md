## MODIFIED Requirements
### Requirement: Free-tier model whitelist for chat endpoints
The system SHALL maintain a comprehensive whitelist of verified zero-cost OpenRouter models with documented capabilities and context limits.

#### Scenario: Expanded free-tier whitelist with Q model
- **WHEN** system initializes chat routing
- **THEN** it defines `FREE_TIER_MODELS` whitelist containing:
  - `google/gemini-2.0-flash-exp:free` (fast, general-purpose, large context)
  - `mistralai/mistral-7b-instruct:free` (balanced chat model)
  - `mistralai/devstral-2512:free` (262K context, code/architecture specialist)
  - `meta-llama/llama-3.1-8b-instruct:free` (general chat)
  - `deepseek/deepseek-r1-0528:free` (164K context, deep reasoning/CoT)
  - `qwen/qwen3-4b:free` (fast, efficient for semantic/text tasks)
- **AND** each model is verified as $0/M input and $0/M output on OpenRouter
- **AND** configuration includes model capabilities documentation (context size, specialty)

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

#### Scenario: Optimized routing for deep reasoning
- **WHEN** system routes `/api/chat/deep` requests
- **THEN** it uses:
  - Primary: `deepseek/deepseek-r1-0528:free` (reasoning specialist with CoT)
  - Secondary: `mistralai/devstral-2512:free` (long context, code-aware fallback)
  - Tertiary: `google/gemini-2.0-flash-exp:free` (high-speed general model)
- **AND** temperature is 0.6 for exploratory reasoning

#### Scenario: Optimized routing for graph/structure analysis
- **WHEN** system routes `/api/chat/graph` requests
- **THEN** it uses:
  - Primary: `mistralai/devstral-2512:free` (code/structure specialist)
  - Secondary: `deepseek/deepseek-r1-0528:free` (reasoning fallback for complex graphs)
  - Tertiary: `google/gemini-2.0-flash-exp:free` (fast general fallback)
- **AND** temperature is 0.1 for strict graph interpretation

#### Scenario: Optimized routing for fast semantic search
- **WHEN** system routes `/api/chat/semantic` requests
- **THEN** it uses:
  - Primary: `google/gemini-2.0-flash-exp:free` (fastest response, good context)
  - Secondary: `qwen/qwen3-4b:free` (fast, efficient alternative)
  - Tertiary: `mistralai/mistral-7b-instruct:free` (balanced fallback)
- **AND** temperature is 0.2 for focused summaries

#### Scenario: Optimized routing for general text queries
- **WHEN** system routes `/api/chat/text` requests
- **THEN** it uses:
  - Primary: `google/gemini-2.0-flash-exp:free` (fast, no-RAG friendly)
  - Secondary: `mistralai/mistral-7b-instruct:free` (balanced chat)
  - Tertiary: `qwen/qwen3-4b:free` (efficient fallback)
- **AND** temperature is 0.3 for natural conversation

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

## ADDED Requirements
### Requirement: Runtime verification of free-tier models
The system SHALL document a pattern for periodically verifying and updating the free-tier model allowlist from OpenRouter.

#### Scenario: Manual verification pattern documented
- **WHEN** operators need to update the free-tier model list
- **THEN** they reference documented steps:
  1. Fetch https://openrouter.ai/api/v1/models (or free models collection)
  2. Filter models where `pricing.prompt === "0"` and `pricing.completion === "0"`
  3. Review model capabilities and context limits
  4. Update `FREE_TIER_MODELS` in configuration
  5. Deploy and monitor fallback metrics
- **AND** this pattern is documented in `llm-service` spec for future automation
- **AND** no automatic updates occur without manual review (deferred to future iteration)

### Requirement: Enhanced LLM reasoning for transformation chains
The system SHALL provide detailed, step-by-step reasoning when answering questions about column traceability or data transformations.

#### Scenario: Column traceability reasoning
- **WHEN** user asks about column lineage (e.g., "Where does user_id come from?")
- **THEN** the LLM response includes:
  - Full transformation chain from source to target
  - Each transformation step with SQL/Python logic excerpt
  - Column name changes between steps
  - Join conditions and filtering logic that affects the column
- **AND** response format shows clear numbered steps with indentation for nested dependencies
- **AND** `graph_data` includes all nodes/edges in the chain with transformation metadata

#### Scenario: Transformation chain explanation
- **WHEN** user asks about data transformations (e.g., "How is fact_orders created?")
- **THEN** the LLM response includes:
  - Source tables/files with relevant columns
  - Each transformation layer (staging → intermediate → mart)
  - Business logic summary for each step
  - SQL/Python code snippets showing key transformations
  - Dependencies between transformation steps
- **AND** response uses clear transitional language ("First... Then... Finally...")
- **AND** highlights WHERE clauses, JOIN conditions, GROUP BY logic that affects output

#### Scenario: Code logic display in evidence
- **WHEN** LLM includes transformation evidence in sources array
- **THEN** each evidence object includes `code_excerpt` field with relevant SQL/Python snippet
- **AND** code excerpts are trimmed to relevant 5-20 lines (not entire file)
- **AND** code includes syntax highlighting hints (language field)
- **AND** code shows context (e.g., "FROM stg_users JOIN stg_events ON...")

### Requirement: Graph metadata enrichment for visualization
The system SHALL include detailed metadata in `graph_data` to enable interactive visualization with code display.

#### Scenario: Node metadata for tables and columns
- **WHEN** graph includes table or column nodes
- **THEN** each node includes metadata:
  - `columns`: array of column names (for tables)
  - `data_type`: column data type (for columns)
  - `description`: human-readable description if available
  - `row_count`: estimated row count (for tables)
  - `sample_values`: example values (for columns, privacy-safe)
- **AND** metadata enables detail panel display without additional API calls

#### Scenario: Edge metadata for transformations
- **WHEN** graph includes transformation edges
- **THEN** each edge includes metadata:
  - `transformation_type`: "SELECT", "JOIN", "GROUP BY", "FILTER", "AGGREGATE", etc.
  - `code_excerpt`: relevant SQL/Python snippet showing the transformation
  - `affected_columns`: list of columns involved in transformation
  - `confidence`: confidence score for LLM-inferred edges
  - `status`: "deterministic" or "proposed"
- **AND** metadata enables edge detail panel with code display

#### Scenario: Code storage for interactive display
- **WHEN** transformation node represents SQL/Python file
- **THEN** node metadata includes:
  - `code`: full file content (or reference to retrieve it)
  - `language`: "sql" or "python"
  - `file_path`: relative path in repository
  - `affected_objects`: list of tables/views created or modified
- **AND** frontend can display code in syntax-highlighted modal on node click
