# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## 1. How to run the backend

### 1.1 Docker (recommended path)

Most day-to-day work should assume the Docker-based stack described in `README.md` and `docs/setup/DOCKER_SETUP.md`.

From the repo root:

```bash
# Validate Docker + Ollama setup
check-docker.bat              # Windows
./check-docker.sh             # macOS/Linux

# Start full stack (API + Qdrant + Redis, etc.)
start-docker.bat
./start-docker.sh

# Tail logs for all services
logs-docker.bat
./logs-docker.sh

# Stop containers (preserve volumes)
stop-docker.bat
./stop-docker.sh

# Restart API container only (when code changes)
docker compose -f docker-compose.local.yml restart api
```

Key URLs once stack is healthy (see `/health`):
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- RAG status: `http://localhost:8000/api/v1/rag/status`

Environment defaults for the Docker stack (see `.env` and `docs/setup/DOCKER_SETUP.md`):
- `OLLAMA_HOST=http://host.docker.internal:11434`
- `QDRANT_HOST=qdrant`
- `REDIS_HOST=redis`
- `USE_LLAMAINDEX=true`

### 1.2 Local Python run (without Docker)

For backend-only development and debugging (e.g., changing FastAPI routers, services, or ingestion logic):

```bash
# Create and activate virtualenv (example; adapt to your shell)
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Unix shells
source .venv/bin/activate

# Install dependencies for the local (Ollama + Qdrant + Neo4j) stack
pip install -r requirements-local.txt

# Run API locally (Ollama + Qdrant + Neo4j)
python src/api/main_local.py
# or with uvicorn for auto-reload
uvicorn src.api.main_local:app --reload --port 8000
```

Assumptions for a working local stack (see `docs/setup/LOCAL_SETUP_GUIDE.md`):
- Ollama is running with at least `llama3.1:8b` and `nomic-embed-text` pulled.
- Qdrant, Redis, and Neo4j are reachable with the host/port values from `.env`.
- `.env` is based on `.env.example` with at minimum:
  - `OLLAMA_HOST`, `LLM_MODEL`, `EMBEDDING_MODEL`
  - `QDRANT_HOST`, `QDRANT_PORT`
  - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
  - `STORAGE_PATH`, `LOG_PATH`

The local app entrypoint is `src/api/main_local.py`. It wires up:
- Local Ollama client (`OllamaClient`)
- Local Qdrant client (`QdrantLocalClient`)
- Neo4j client (`Neo4jGraphClient`)
- Optional LlamaIndex RAG service (`LlamaIndexService`) when `USE_LLAMAINDEX=true`
- Lineage supervisor agent (`LocalSupervisorAgent`)
- DuckDB-backed metadata store and upload settings

### 1.3 Building containers directly

When you need to build/push images (outside the helper scripts):

```bash
# Production-style image (uses requirements.txt)
docker build -t financial-lineage-tool-backend .

# Local-dev image (uses requirements-local.txt and main_local)
docker build -f Dockerfile.local -t financial-lineage-tool-backend-local .
```

## 2. Testing, linting, and formatting

### 2.1 Pytest

Tests are organized under `tests/` into unit, integration, and performance suites.

From repo root:

```bash
# Full test suite
pytest tests/ -v

# Integration tests only (requires services running, typically via Docker)
pytest tests/ -v -m integration

# Coverage
pytest tests/ --cov=src --cov-report=html
```

Running an individual test file or test:

```bash
# Single file
pytest tests/unit/api/test_files_router.py -vv

# Single test within a file
pytest tests/unit/api/test_files_router.py::test_upload_file_happy_path -vv
```

`requirements-test.txt` adds extra tooling (e.g., `schemathesis`) for API contract testing; prefer using it in CI or when doing API-level regression work.

### 2.2 Linters and type-checking

The project uses Black, Ruff, and MyPy (see `requirements.txt` and `requirements-local.txt`). Typical commands:

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type checking
mypy src
```

If a `pyproject.toml` or tool-specific config exists, respect the configured paths/ignores; otherwise default to `src` and `tests`.

## 3. High-level architecture

The backend is a FastAPI application that exposes lineage, graph, ingestion, and chat endpoints over a layered architecture:

### 3.1 Runtime layers

- **API layer (`src/api/`)**
  - `main_local.py` – FastAPI entrypoint for the local (Ollama/Qdrant/Neo4j) stack; configures lifespan, initializes external services, and mounts routers.
  - `config.py` – central runtime configuration object (`config`) sourced from environment variables; includes paths, model names, ports, and feature flags such as `USE_LLAMAINDEX`.
  - `middleware/` – CORS, activity tracking, and error handling.
  - `models/` – Pydantic request/response models for chat, lineage, ingest, graph, health, project metadata, etc.
  - `routers/` – domain-specific routers:
    - `health.py` – `/health` and RAG status/metrics endpoints.
    - `chat.py` – `/api/chat/*` endpoints for deep/semantic/graph/text chat.
    - `lineage.py` – `/api/v1/lineage/*` lineage-facing endpoints.
    - `ingest.py` – ingestion endpoints (files, SQL content).
    - `graph.py` – raw graph CRUD and stats.
    - `admin.py` – dashboard stats, model listing, WebSocket dashboard, restart.
    - `database.py`, `files.py`, `github.py`, `metadata.py`, `projects.py` – schema/file/project/GitHub/metadata utilities.

- **Services layer (`src/services/`)**
  - `ollama_service.py` – thin async client over Ollama’s HTTP API. Handles chat, embeddings, and Redis-backed embedding cache with TTL.
  - `qdrant_service.py` – lightweight HTTP client for Qdrant (create collection, upsert, search) used in the “legacy” RAG path.
  - `agent_service.py` – `LocalSupervisorAgent`, which:
    - Embeds the user question via Ollama.
    - Queries Qdrant for relevant `code_chunks`.
    - Queries Neo4j for candidate entities and their upstream/downstream lineage.
    - Builds a combined context and prompts the LLM with a lineage-focused system prompt.
  - `memory_service.py` – long-term chat memory backed by Qdrant (imported by `main_local.py`).
  - `ingestion_tracker.py`, `ollama_service.py`, `qdrant_service.py` – used by routers, RAG pipeline, and UI dashboards.

- **LLM & RAG (`src/llm/`)**
  - `llamaindex_service.py` – the primary RAG implementation when `USE_LLAMAINDEX=true`:
    - Wraps LlamaIndex with Ollama-based LLM + embedding models.
    - Uses `QdrantVectorStore` with both sync and async clients.
    - Provides `index_documents` / `index_code_chunks` helpers for feeding `CodeChunk` objects into Qdrant.
    - Exposes `query(...)` that returns the answer string, source snippets (with metadata), latency metrics, and cache statistics.
    - Uses Redis to cache both embeddings and full query responses, with per-key TTLs and rolling latency averages.

- **Knowledge graph (`src/knowledge_graph/`)**
  - `neo4j_client.py` – high-level Neo4j client wrapping GraphDatabase driver.
    - Responsible for entity CRUD, lineage traversal (`get_upstream` / `get_downstream`), index creation, and stats.
    - All lineage graph data travels through this abstraction; Neo4j credentials and database name are provided via env.
  - `entity_extractor.py` – converts parsed/organized SQL structures into graph entities and relationships (tables, columns, views, foreign keys, etc.), calling into `Neo4jGraphClient`.

- **Ingestion & organization (`src/ingestion/`)**
  - `semantic_chunker.py` – central AST-aware chunker:
    - SQL: uses `sqlglot` to detect CTEs, statements, and subqueries; keeps related CTEs together where possible; carries CTE dependency info as a `context_prefix` for better embeddings.
    - Python: uses the Python AST to carve out import blocks, functions, classes, and methods; preserves decorators and docstrings; attaches simple table-reference heuristics.
    - Falls back to token-bounded generic chunking for unknown languages.
    - Emits `CodeChunk` objects enriched with table/column metadata and token counts.
  - `hierarchical_organizer.py` and `enhanced_sql_parser.py` – implement the SQL Server–aware hierarchical file layout documented in `docs/architecture/IMPLEMENTATION_STATUS.md` and `docs/guides/HIERARCHICAL_ORGANIZATION_GUIDE.md`.
  - `file_watcher.py` – `SQLFileWatcher` that monitors `data/raw/` (via `watchdog`) and feeds new/updated `.sql` files through the hierarchical organizer into `data/separated_sql/`.
  - `batch_processor.py`, `worker_pool.py`, `parallel_file_watcher.py`, `cpu_bound_parser.py`, `parse_cache.py`, `corpus.py` – parallel and cached ingestion pipelines for larger corpora.

- **Search (`src/search/`)**
  - `hybrid_search.py` – higher-level search abstraction used by agents to combine vector similarity with metadata filtering; current local stack uses Qdrant plus embeddings from Ollama.

- **Storage & metadata (`src/storage/`)**
  - `duckdb_client.py` – initializes and manages a DuckDB database for local metadata storage (e.g., upload settings, ingestion stats).
  - `metadata_store.py` – CRUD operations over metadata entities and projects; `ensure_default_project()` is called during app startup.
  - `upload_settings.py` – persisted upload configuration (allowed extensions, max file size) that can override `config` at startup.
  - `archive.py`, `artifact_manager.py` – archival and artifact-management utilities for exports and snapshots.

- **Utilities & config (`src/utils/`, `src/config/`)**
  - `data_paths.py` – centralizes derived paths for data, logs, and exports.
  - `logging_config.py` – structured logging configuration using `structlog`.
  - `activity_tracker.py`, `metrics.py` – request-level tracking and metrics surfaced via health and admin endpoints.
  - `feature_flags.py` – feature toggles (e.g., enabling LlamaIndex, parallel ingestion strategies, dashboard features).

### 3.2 Ingestion and indexing flow (SQL → graph + embeddings)

At a high level, the ingestion pipeline follows the design in `docs/architecture/ARCHITECTURE.md` and `docs/architecture/IMPLEMENTATION_STATUS.md`:

1. **SQL organization**
   - Raw SQL is dropped into `data/raw/`.
   - Either run a one-shot script (`examples/test_hierarchical_organizer.py`) or start the continuous watcher (`python examples/start_file_watcher.py`).
   - Hierarchical organizer writes normalized objects under `data/separated_sql/{DatabaseName}/...` (tables, views, procedures, etc.), plus manifests with statistics.

2. **Semantic chunking**
   - Organized SQL (and optionally Python/config code) is fed into `SemanticChunker`.
   - For each `CodeChunk`, we capture table/column references and a context-rich prefix, and compute token counts using `tiktoken`.

3. **Indexing to vector store**
   - `LlamaIndexService.index_code_chunks(...)` converts `CodeChunk`s to LlamaIndex `Document`s with rich metadata (file path, chunk type, tables, columns, dependencies, token counts).
   - Documents are indexed into the `code_chunks` Qdrant collection (768-dim cosine vectors) via the Qdrant vector store.

4. **Graph population**
   - `entity_extractor` reads organized SQL/parsed structures, creates table/column/view/procedure entities, and pushes them into Neo4j through `Neo4jGraphClient`.
   - Relationships (e.g., `has_column`, foreign keys, dependencies) are represented as edges; indexes are created for fast traversal.

### 3.3 Query and RAG flow

There are two main query paths, controlled by `USE_LLAMAINDEX` and availability of `LlamaIndexService` (see `docs/architecture/LLAMAINDEX_RAG.md`):

1. **LlamaIndex RAG path (preferred)**
   - Chat or lineage endpoints receive a question.
   - `LlamaIndexService.query(...)`:
     - Computes a cache key and checks Redis for a cached answer.
     - Uses a query engine over the Qdrant-backed index to retrieve top-k chunks.
     - Synthesizes an answer using Ollama (`llama3.1:8b` by default).
     - Returns the answer, source chunks with metadata, latency, and RAG metrics; results are cached in Redis for subsequent identical queries.
   - `/api/v1/rag/status` surfaces current RAG metrics.

2. **Legacy LocalSupervisorAgent path**
   - Used when LlamaIndex is disabled or initialization fails.
   - `LocalSupervisorAgent.query(...)`:
     - In parallel: embeds the question and searches Qdrant, and batch-queries Neo4j for entities.
     - Builds an in-memory lineage graph for the most relevant entities (upstream/downstream) and a file-centric code context.
     - Prompts Ollama with a structured system prompt to produce a lineage-oriented answer.
     - Returns answer text, source file paths, a graph payload (`nodes`/`edges`) suitable for visualization, and a coarse confidence score.

Both paths share the same underlying `OllamaClient` and `QdrantLocalClient` instances configured by `main_local.py`.

## 4. Specs, docs, and AI-assistant rules

### 4.1 OpenSpec / CLAUDE instructions

For any work that involves planning, proposals, specs, or significant architectural/performance/security changes:

- **Always read** `openspec/AGENTS.md` before making changes.
- The managed block in `CLAUDE.md` defines when to treat a task as an OpenSpec change:
  - The request mentions proposals/specs/plans or otherwise sounds like upfront design is required.
  - The change introduces new capabilities, breaking changes, architecture shifts, or large performance/security work.
- Use the OpenSpec docs in `openspec/` (`project.md`, `specs/`, `changes/`) to align with existing proposal and spec formats before editing core modules.

If you are asked to “write a spec”, “draft a proposal”, or “plan a large refactor”, prefer generating or updating an OpenSpec change document under `openspec/changes/` rather than making ad-hoc notes.

### 4.2 Repository docs to consult first

When an instruction or behavior is ambiguous, prefer the following documentation sources over inferring from code alone:

- `README.md` – high-level project overview, Docker quickstart, testing commands, and primary entrypoints.
- `docs/README.md` – documentation hub, linking to:
  - `docs/setup/DOCKER_SETUP.md` – canonical source for Docker workflows and service layout.
  - `docs/setup/LOCAL_SETUP_GUIDE.md` – authoritative guide for the local (Ollama + Qdrant + Neo4j) stack used by `main_local.py`.
  - `docs/architecture/ARCHITECTURE.md` – authoritative description of layers, main modules, and data flows.
  - `docs/architecture/LLAMAINDEX_RAG.md` – details of the LlamaIndex-based RAG pipeline.
  - `docs/architecture/IMPLEMENTATION_STATUS.md` – what is complete vs. planned in the ingestion and lineage system.
  - `docs/api/API_REFERENCE.md` – API contracts; use this when modifying routers or models.
- `docs/guides/*` – workflow-oriented guides (SQL organizer, file watcher, exports, etc.) that explain how the ingestion pieces are meant to be used together.

### 4.3 Legacy Copilot instructions

The file `.github/copilot-instructions.md` describes an earlier Azure-based deployment (Azure OpenAI, Cosmos Gremlin, Azure Search). The **big-picture concepts** remain relevant and should still guide changes:

- The system is an AI-driven data lineage service that:
  - Ingests SQL/Python code and organizes it into semantic chunks.
  - Builds a lineage knowledge graph over entities and relationships.
  - Supports natural language lineage questions via an agent/orchestrator layer.
- Changes that affect ingestion, graph structure, or query behavior should flow through the corresponding abstraction layers (ingestion modules, `Neo4jGraphClient`, `LlamaIndexService` or `LocalSupervisorAgent`), rather than bypassing them.

When there is a conflict between `.github/copilot-instructions.md` and the current local stack (Ollama/Qdrant/Neo4j), prefer **current code and `docs/architecture/*`**.

## 5. Assistant-focused implementation notes

- When adding **new lineage or RAG features**:
  - Check `src/config/feature_flags.py` for relevant toggles and consider wiring new behavior behind a flag if it could be disruptive.
  - If the feature relies on vector search, prefer integrating it via `LlamaIndexService` where possible; keep the Qdrant collection name and embedding dimension consistent (`code_chunks`, 768-dim).
  - If it needs graph data, add/query capabilities through `Neo4jGraphClient` instead of issuing raw Cypher from scattered locations.

- When modifying **chat or lineage endpoints**:
  - Update the corresponding router under `src/api/routers/` and ensure the change is reflected in `docs/api/API_REFERENCE.md` when contracts evolve.
  - Keep the distinction between RAG modes clear (`USE_LLAMAINDEX` on vs. off) and ensure both paths degrade gracefully when a dependency (Ollama, Qdrant, Neo4j, Redis) is unavailable.

- When extending **ingestion**:
  - Reuse or extend `SemanticChunker` and `CodeChunk` rather than inventing new representations; downstream RAG and search logic expect the existing metadata fields.
  - For additional SQL dialect quirks or languages, add to the existing chunkers (or language map) so all ingest paths benefit.

These guidelines, combined with the commands and architecture notes above, should be sufficient for future Warp agents to be productive in this repository without rediscovering the overall design.
