# Financial Lineage Tool - Backend Architecture

## Table of Contents
- [Overview](#overview)
- [Architecture Diagram](#architecture-diagram)
- [Code Structure](#code-structure)
- [API Layer](#api-layer)
- [Services Layer](#services-layer)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)

## Overview

The Financial Lineage Tool backend is a FastAPI-based application that provides REST API endpoints for SQL code analysis, data lineage tracking, and natural language queries about database structures. The architecture follows a **layered pattern** with clear separation of concerns.

### Design Principles

1. **Layered Architecture**: API → Services → Domain Logic
2. **Separation of Concerns**: Each module has a single, well-defined responsibility
3. **Dependency Injection**: Services are initialized at startup and injected where needed
4. **Type Safety**: Comprehensive type hints throughout the codebase
5. **Documentation-First**: All functions and classes include detailed docstrings

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Applications                      │
│                    (Frontend, CLI, API Clients)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    API Layer (Routers)                      │ │
│  │  • Health     • Chat      • Lineage                        │ │
│  │  • Ingest     • Graph     • Admin                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      Middleware                             │ │
│  │  • CORS              • Activity Tracking                   │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Services Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Ollama     │  │   Qdrant     │  │    Agent     │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────────────────────────────────────────┐          │
│  │              LlamaIndex Service                   │          │
│  │    (RAG Pipeline with Redis Caching)             │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐    ┌──────────────┐
│   Ollama     │     │   Qdrant     │    │    Neo4j     │
│  (LLM Host)  │     │ (Vector DB)  │    │ (Graph DB)   │
└──────────────┘     └──────────────┘    └──────────────┘
        ▲                    ▲                    ▲
        │                    │                    │
        └────────────────────┴────────────────────┘
                      Redis (Cache)
```

## Code Structure

```
src/
├── api/                          # API Layer
│   ├── main_local.py            # FastAPI app (253 lines)
│   ├── config.py                # Configuration management
│   ├── middleware/              # HTTP middleware
│   │   ├── cors.py             # CORS configuration
│   │   └── activity.py         # Request tracking
│   ├── models/                  # Pydantic models
│   │   ├── chat.py             # Chat request/response
│   │   ├── health.py           # Health check models
│   │   ├── graph.py            # Graph operation models
│   │   ├── ingest.py           # Ingestion models
│   │   ├── lineage.py          # Lineage query models
│   │   └── schema.py           # Database schema models
│   └── routers/                 # API endpoints (26 total)
│       ├── health.py           # Health & monitoring (4 endpoints)
│       ├── chat.py             # Chat interfaces (4 endpoints)
│       ├── lineage.py          # Lineage queries (4 endpoints)
│       ├── ingest.py           # Data ingestion (2 endpoints)
│       ├── graph.py            # Graph operations (5 endpoints)
│       └── admin.py            # Admin & files (7 endpoints)
│
├── services/                    # Services Layer
│   ├── ollama_service.py       # Ollama LLM client
│   ├── qdrant_service.py       # Qdrant vector DB client
│   └── agent_service.py        # Supervisor agent for queries
│
├── llm/                         # LLM Integration
│   └── llamaindex_service.py   # LlamaIndex RAG pipeline
│
├── ingestion/                   # Code Processing
│   ├── code_parser.py          # SQL parser
│   ├── semantic_chunker.py     # Code chunking
│   └── hierarchical_organizer.py
│
├── knowledge_graph/             # Graph Database
│   ├── neo4j_client.py         # Neo4j operations
│   └── entity_extractor.py     # Entity extraction
│
├── agents/                      # Multi-Agent System
│   └── supervisor.py           # Legacy supervisor (deprecated)
│
└── utils/                       # Utilities
    ├── exceptions.py           # Custom exceptions
    ├── constants.py            # Application constants
    ├── types.py                # Type aliases
    ├── validators.py           # Input validation
    ├── logging_config.py       # Logging setup
    └── activity_tracker.py     # Activity metrics
```

## Parser Plugins

Lineage parsing uses a plugin registry. Plugins are loaded from `LINEAGE_PLUGINS`
and selected by file extension. Each plugin returns a standardized `LineageResult`
with nodes, edges, and external references, which is ingested into Neo4j.

```
File Content
  |
  v
PluginRegistry -> LineagePlugin.parse() -> LineageResult
  |
  v
GraphExtractor.ingest_lineage_result() -> Neo4j
```

Key plugins:
- StandardSqlPlugin (sqlglot)
- PythonTreesitterPlugin (tree-sitter + AST fallback)
- JsonEnricherPlugin (metadata enrichment)

### Parsing fallback behavior

When a plugin is not available for a file type, ingestion falls back to the
legacy parsers in the graph extractor (SQL/Python/JSON). The validation agent
skips in that case because it requires a plugin to rebuild expectations.

### Hybrid Search Example

```python
query_embedding = await ollama.embed("gross margin by product", model="nomic-embed-text")
results = await qdrant.hybrid_search(
    "code_chunks",
    query_text="gross margin by product",
    dense_vector=query_embedding,
    limit=5,
)
```

### OpenRouterService Example

```python
service = OpenRouterService(api_key="...", default_model="google/gemini-2.0-flash-exp:free")
edges = await service.predict_lineage(code_snippet, context_nodes)
```

## API Layer

### Routers

The API is organized into **6 focused routers**, each handling a specific domain:

#### 1. Health Router (`/health`, `/api/v1/rag/status`, `/api/v1/metrics/*`)
**Purpose**: System health monitoring and metrics

**Endpoints**:
- `GET /health` - Check all services (Ollama, Qdrant, Neo4j, Redis)
- `GET /api/v1/rag/status` - RAG pipeline status and metrics
- `GET /api/v1/metrics/activity` - Activity tracking metrics
- `GET /api/v1/metrics/events` - Recent activity events

#### 2. Chat Router (`/api/chat/*`)
**Purpose**: Interactive chat interfaces for code queries

**Endpoints**:
- `POST /api/chat/deep` - Deep analysis with comprehensive context (top 10 results)
- `POST /api/chat/semantic` - Semantic search using embeddings
- `POST /api/chat/graph` - Graph-based queries for relationships
- `POST /api/chat/text` - Simple LLM queries without RAG

#### 3. Lineage Router (`/api/v1/lineage/*`)
**Purpose**: Data lineage queries and graph traversal

**Endpoints**:
- `POST /api/v1/lineage/query` - Natural language lineage queries
- `GET /api/v1/lineage/nodes` - Get all graph nodes
- `GET /api/v1/lineage/edges` - Get all graph edges
- `GET /api/v1/lineage/search` - Search for entities by name
- `GET /api/v1/lineage/node/{node_id}` - Get lineage for specific node

#### 4. Ingest Router (`/api/v1/ingest/*`)
**Purpose**: Code ingestion and processing

**Endpoints**:
- `POST /api/v1/ingest` - Ingest files (background processing)
- `POST /api/v1/ingest/sql` - Ingest raw SQL content

#### 5. Graph Router (`/api/v1/graph/*`)
**Purpose**: Knowledge graph CRUD operations

**Endpoints**:
- `GET /api/v1/graph/stats` - Graph statistics
- `POST /api/v1/graph/entity` - Add entity to graph
- `POST /api/v1/graph/relationship` - Add relationship
- `GET /api/v1/graph/entity/{entity_id}` - Get entity by ID
- `GET /api/v1/graph/search` - Search entities by name
- `GET /api/v1/graph/lineage/{entity_id}` - Get entity lineage

#### 6. Admin Router (`/api/v1/*`)
**Purpose**: Dashboard, files, and administration

**Endpoints**:
- `GET /api/v1/models` - List available Ollama models
- `GET /api/v1/stats` - Dashboard statistics
- `GET /api/v1/activity/recent` - Recent activity
- `GET /api/v1/files/recent` - Recently processed files
- `GET /api/v1/files` - List all files
- `GET /api/v1/files/stats` - File statistics
- `GET /api/v1/files/search` - Search files

### Middleware

**CORS Middleware**: Handles cross-origin requests (configured for all origins in development)

**Activity Tracking Middleware**: Tracks all requests for monitoring and analytics:
- Records endpoint, method, status code
- Measures latency
- Classifies event types (query, ingest, health_check, error)
- Stores in Redis for metrics aggregation

### Models

All request/response models use **Pydantic** for validation and serialization:
- **Type safety**: Full type hints
- **Validation**: Automatic input validation
- **Serialization**: JSON encoding/decoding
- **Documentation**: Auto-generated OpenAPI specs

## Services Layer

### OllamaClient (`services/ollama_service.py`)

**Purpose**: Interface to local Ollama LLM server

**Key Methods**:
- `generate(prompt, model, system, temperature)` - Text generation
- `embed(text, model)` - Generate embeddings

**Features**:
- Async HTTP client with 120s timeout
- Supports any Ollama-compatible model
- Error handling with detailed messages

### QdrantLocalClient (`services/qdrant_service.py`)

**Purpose**: Vector database operations

**Key Methods**:
- `create_collection(name, vector_size)` - Initialize collection
- `upsert(collection, points)` - Add/update vectors
- `search(collection, vector, limit, filters)` - Similarity search

**Features**:
- Cosine similarity distance
- Metadata filtering support
- Batch upsert operations

### LocalSupervisorAgent (`services/agent_service.py`)

**Purpose**: Orchestrates RAG queries combining vector search and graph traversal

**Query Pipeline**:
1. **Vector Search**: Find relevant code using embeddings
2. **Graph Search**: Extract entities mentioned in query
3. **Lineage Retrieval**: Get upstream/downstream dependencies
4. **Context Building**: Combine code snippets and graph data
5. **LLM Generation**: Generate answer using Ollama

**Configuration**:
- Configurable LLM and embedding models
- Adjustable search depth and result limits
- Confidence scoring based on available context

### LlamaIndexService (`llm/llamaindex_service.py`)

**Purpose**: Advanced RAG pipeline with caching

**Features**:
- Query and embedding caching via Redis
- Metrics tracking (cache hit rates, latency)
- Session-based activity logging
- Ollama integration for LLM and embeddings

### OpenRouterService (`services/inference_service.py`)

**Purpose**: Free-tier LLM routing and lineage edge proposal generation.

**Features**:
- Enforces free-tier model whitelist
- Strict JSON parsing for structured edge proposals
- Fallback routing when non-free models are requested

### ValidationAgent (`services/validation_agent.py`)

**Purpose**: Post-ingestion verification of parsed results against Neo4j state.

**Features**:
- Re-parses content with the active plugin
- Detects missing nodes/edges by URN ID
- Emits structured validation summaries for ingestion logs

### KGEnrichmentAgent (`services/kg_enrichment_agent.py`)

**Purpose**: Augment the knowledge graph with LLM-proposed edges.

**Features**:
- Uses OpenRouter Devstral free-tier model
- Writes accepted edges to Neo4j with provenance metadata
- Logs proposals and acceptance metrics per ingestion run

## Data Flow

### 1. Ingestion Flow

```
SQL File → SemanticChunker → Code Chunks
                                    ↓
                          ┌─────────┴─────────┐
                          ▼                   ▼
                    Ollama (embed)      GraphExtractor
                          ↓                   ↓
                    Qdrant (store)      Neo4j (store)
```

**Run-scoped sequence**
1. Create run context and directories (`raw_source/`, `chunks/`, `validations/`, `KG/`).
2. Pre-ingestion snapshot (project/file scoped) written to run `KG/`.
3. Purge existing Qdrant and Neo4j assets for the file path.
4. Parse via plugin (or fallback parser) and write to Neo4j.
5. Chunk and persist embeddings payloads under `embeddings/`, then index into Qdrant.
6. Validation agent checks Neo4j vs parsed expectations.
7. KG enrichment agent proposes/creates additional edges.
8. Post-ingestion snapshot written to run `KG/`.
9. Artifact validation verifies expected files; failures trigger purge cleanup.

### 1a. Post-Ingestion Validation and KG Enrichment

After ingestion writes to Neo4j, the pipeline runs two post-processing steps:

- Pre/post ingestion snapshots: exports scoped nodes and edges to
  `data/{project}/{run}/KG/neo4j_snapshot_{phase}_{timestamp}_{ingestion_id}.json`.
- Validation agent: re-parses content with the active plugin and checks for missing
  nodes or edges in Neo4j, reporting gap counts.
- KG enrichment agent: uses OpenRouter Devstral (free-tier) to propose edges and
  writes accepted edges with metadata (`source=llm`, `model`, `confidence`, `status`).

Ingestion logs capture stage events for `graph_snapshot`, `validation`, and
`kg_enrichment` with paths, counts, and confidence summaries.

#### Validation agent details

The validation agent re-parses the ingested content and compares expected entities
to what was actually written in Neo4j.

**How it works**
- Re-parses the file using the active plugin and dialect (same parser as ingestion).
- Builds expected nodes from `LineageResult.nodes` and `LineageResult.external_refs`.
- Builds expected edges from `LineageResult.edges`, keyed by `(source_id, target_id, relationship_type)`.
- Generates expected node IDs using URNs (`urn:li:{label}:{project_id}:{asset_path}`) to match ingestion IDs.
- Fetches existing nodes and edges in Neo4j by ID to detect gaps.

**Output**
- Produces a `ValidationSummary` with:
  - `status`: `passed`, `failed`, `skipped`, or `error`
  - `expected_nodes`, `expected_edges`
  - `missing_nodes`, `missing_edges` (full records for triage)
- Written to `data/{project}/{run}/validations/*_validation.json` and logged in the ingestion log.

**Limitations**
- Checks presence only (does not compare full property sets).
- Skips when no plugin is available for the file type.
- Does not detect extra nodes/edges in Neo4j (only missing).
- Depends on deterministic URN generation for ID matching.

### 1b. Run-scoped artifacts and cleanup

Each ingestion run stores all artifacts under `data/{project}/{run}/`:
- `raw_source/` original file copy
- `chunks/` object-split chunk outputs
- `embeddings/` embedding payloads recorded before Qdrant upsert
- `validations/` validation summaries
- `KG/` pre/post Neo4j snapshots

If required artifacts are missing after ingestion, the pipeline purges Neo4j and
Qdrant data for the file to keep the knowledge graph in sync.

### 2. Query Flow (LlamaIndex Enabled)

```
User Query → LlamaIndexService
                 ↓
         Check Redis Cache
                 ↓
         (miss) → Generate Embedding → Search Qdrant
                                            ↓
                                      Retrieve Context
                                            ↓
                                       Ollama (LLM)
                                            ↓
                                     Cache Response
                                            ↓
                                     Return to User
```

### 3. Query Flow (Legacy Mode)

```
User Query → LocalSupervisorAgent
                 ↓
         ┌───────┴───────┐
         ▼               ▼
    Vector Search   Graph Search
    (via Qdrant)   (via Neo4j)
         ↓               ↓
         └───────┬───────┘
                 ▼
         Build Context
                 ↓
         Ollama Generate
                 ↓
         Return Response
```

## Technology Stack

### Core Framework
- **FastAPI**: Modern async web framework
- **Pydantic**: Data validation and serialization
- **Python 3.10+**: Type hints, async/await

### LLM & Embeddings
- **Ollama**: Local LLM inference (Llama 3.1 8B)
- **nomic-embed-text**: Embedding model (768 dimensions)
- **LlamaIndex**: RAG framework

### Databases
- **Qdrant**: Vector similarity search
- **Neo4j**: Graph database for lineage
- **Redis**: Query and embedding cache

### Code Quality
- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking

### Development
- **Docker**: Containerization
- **Docker Compose**: Multi-service orchestration
- **pytest**: Testing framework

## Configuration

Configuration is managed via environment variables loaded from `.env`:

```python
# Ollama
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text

# LlamaIndex
USE_LLAMAINDEX=true
SIMILARITY_TOP_K=5

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=code_chunks

# Neo4j
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Storage
STORAGE_PATH=./data
LOG_PATH=./logs
```

## Performance Considerations

### Caching Strategy
- **Query Cache**: 1 hour TTL
- **Embedding Cache**: 24 hour TTL
- **Cache Keys**: SHA256 hash of query/content

### Optimization
- **Async I/O**: All database and LLM calls are async
- **Connection Pooling**: Reused HTTP clients
- **Batch Processing**: File ingestion in background
- **Index Optimization**: Neo4j indexes on entity IDs and names

### Scalability
- **Stateless API**: Can run multiple instances
- **External State**: All state in databases (Qdrant, Neo4j, Redis)
- **Background Tasks**: Long-running operations don't block requests

## Error Handling

### Custom Exception Hierarchy
```python
LineageToolError (base)
├── ConfigurationError
├── IngestionError
├── VectorStoreError
├── GraphDatabaseError
├── LLMError
└── ValidationError
```

### Error Responses
- **503 Service Unavailable**: Service not initialized
- **404 Not Found**: Entity or file not found
- **500 Internal Server Error**: Unexpected errors
- **400 Bad Request**: Invalid input

## Monitoring & Observability

### Activity Tracking
- All requests logged with metadata
- Latency measurement per endpoint
- Event classification (query, ingest, error)
- Redis-backed metrics storage

### Health Checks
- Service connectivity checks (Ollama, Qdrant, Neo4j)
- RAG pipeline status
- Cache hit rates
- Query latency metrics

### Metrics Available
- Total queries processed
- Cache hit rate (query and embedding)
- Average latency per endpoint
- Error rates by type
- Top endpoints by usage

## Security Considerations

### Current Implementation
- **CORS**: Configured for all origins (development)
- **No Authentication**: Open API (for development)
- **Input Validation**: Pydantic model validation
- **SQL Injection**: Using parameterized queries

### Production Recommendations
- Implement authentication (OAuth2, JWT)
- Restrict CORS to specific origins
- Add rate limiting
- Enable HTTPS
- Secure Neo4j credentials
- Regular security audits

## Future Enhancements

### Planned Features
1. **Authentication & Authorization**: User management and API keys
2. **Advanced Caching**: Semantic cache for similar queries
3. **Query Optimization**: Query plan analysis
4. **Batch APIs**: Bulk ingestion and queries
5. **Webhooks**: Event notifications for completed processing
6. **Multi-tenant Support**: Isolated data per organization

### Performance Improvements
1. **Vector Index Optimization**: HNSW parameter tuning
2. **Graph Query Optimization**: Cypher query optimization
3. **Parallel Processing**: Multi-threaded code parsing
4. **Smart Caching**: Predictive cache warming

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for development guidelines and code standards.

## License

[Add your license information here]
