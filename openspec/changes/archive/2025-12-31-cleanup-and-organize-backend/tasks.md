# Tasks: Backend Code Cleanup and Organization

## Phase 1: Prepare (Foundation)

### 1.1 Create new directory structure
- [ ] Create `src/api/routers/` directory
- [ ] Create `src/api/middleware/` directory
- [ ] Create `src/api/models/` directory
- [ ] Create `src/services/` directory
- [ ] Create `src/utils/exceptions.py`
- [ ] Create `src/utils/validators.py`
- [ ] Create `src/utils/constants.py`
- [ ] Create `src/utils/types.py`
- [ ] **Validate:** Directory structure exists

### 1.2 Set up logging infrastructure
- [ ] Create `src/utils/logging_config.py` with standard formatter
- [ ] Add request ID middleware for tracking
- [ ] Configure log levels via environment variables
- [ ] Add structured logging examples
- [ ] **Validate:** Log configuration loads without errors

### 1.3 Add type hints infrastructure
- [ ] Add `from __future__ import annotations` to all files
- [ ] Create `src/utils/types.py` with common type aliases
- [ ] Install mypy for type checking
- [ ] Add mypy configuration to `pyproject.toml`
- [ ] **Validate:** `mypy --strict src/` runs (warnings OK for now)

### 1.4 Format existing code
- [ ] Run `black src/` to format all files
- [ ] Run `ruff check src/ --fix` to auto-fix issues
- [ ] Commit formatting changes separately
- [ ] **Validate:** `black --check src/` passes

## Phase 2: Extract and Modularize API

### 2.1 Extract health router
- [ ] Create `src/api/routers/health.py`
- [ ] Move `/health` endpoint from main_local.py
- [ ] Move health check models
- [ ] Add comprehensive docstrings
- [ ] **Validate:** `curl http://localhost:8000/health` returns 200

### 2.2 Extract chat router
- [ ] Create `src/api/routers/chat.py`
- [ ] Move `/api/chat/*` endpoints
- [ ] Move ChatRequest/ChatResponse models to `src/api/models/chat.py`
- [ ] Add docstrings and type hints
- [ ] **Validate:** RAG query endpoint works

### 2.3 Extract lineage router
- [ ] Create `src/api/routers/lineage.py`
- [ ] Move `/api/v1/lineage/*` endpoints
- [ ] Move lineage models to `src/api/models/lineage.py`
- [ ] Add docstrings
- [ ] **Validate:** Lineage query endpoint works

### 2.4 Extract ingest router
- [ ] Create `src/api/routers/ingest.py`
- [ ] Move `/api/v1/ingest/*` endpoints
- [ ] Move ingest models to `src/api/models/ingest.py`
- [ ] Add comprehensive logging
- [ ] **Validate:** File ingestion works

### 2.5 Extract graph router
- [ ] Create `src/api/routers/graph.py`
- [ ] Move `/api/v1/graph/*` endpoints
- [ ] Move graph models to `src/api/models/graph.py`
- [ ] Add docstrings
- [ ] **Validate:** Graph endpoints work

### 2.6 Extract admin router
- [ ] Create `src/api/routers/admin.py`
- [ ] Move `/admin/*` and `/api/v1/metrics/*` endpoints
- [ ] Add admin authentication decorator (placeholder)
- [ ] Move metrics models to `src/api/models/metrics.py`
- [ ] **Validate:** Metrics endpoint returns data

### 2.7 Extract configuration
- [ ] Create `src/api/config.py`
- [ ] Move `LocalConfig` class
- [ ] Add environment variable validation
- [ ] Document all config options
- [ ] **Validate:** Configuration loads correctly

### 2.8 Extract middleware
- [ ] Create `src/api/middleware/activity_tracking.py`
- [ ] Move activity tracking middleware
- [ ] Create `src/api/middleware/cors.py` for CORS setup
- [ ] Add logging middleware
- [ ] **Validate:** Middleware chains correctly

### 2.9 Refactor main.py
- [ ] Rename `main_local.py` to `main.py`
- [ ] Keep only app factory and lifespan
- [ ] Include all routers
- [ ] Register middleware
- [ ] Reduce to < 200 lines
- [ ] **Validate:** API starts and Swagger UI works

## Phase 3: Reorganize Services

### 3.1 Create service layer
- [ ] Create `src/services/llm_service.py` (wrapper for LlamaIndexService)
- [ ] Create `src/services/graph_service.py` (wrapper for Neo4j operations)
- [ ] Create `src/services/vector_service.py` (wrapper for Qdrant)
- [ ] Create `src/services/ingestion_service.py`
- [ ] **Validate:** Services can be imported

### 3.2 Move LLM components
- [ ] Move `src/llm/llamaindex_service.py` to `src/services/llm/llamaindex_service.py`
- [ ] Create `src/services/llm/__init__.py` with exports
- [ ] Update imports in routers
- [ ] Add backward-compatible import in old location
- [ ] **Validate:** LlamaIndex service works

### 3.3 Reorganize knowledge graph
- [ ] Move `src/knowledge_graph/neo4j_client.py` to `src/services/graph/neo4j_client.py`
- [ ] Move `src/knowledge_graph/entity_extractor.py` to `src/services/graph/extractor.py`
- [ ] Update imports
- [ ] Add backward-compatible imports
- [ ] **Validate:** Graph operations work

### 3.4 Reorganize ingestion modules
- [ ] Create `src/ingestion/chunking/semantic_chunker.py`
- [ ] Create `src/ingestion/parsing/code_parser.py`
- [ ] Create `src/ingestion/monitoring/file_watcher.py`
- [ ] Update imports
- [ ] **Validate:** Ingestion pipeline works

## Phase 4: Delete Deprecated Code

### 4.1 Remove unused API files
- [ ] Delete `src/api/main.py` (Azure version)
- [ ] Remove commented Azure imports
- [ ] **Validate:** No broken imports

### 4.2 Remove unused database clients
- [ ] Delete `src/knowledge_graph/cosmos_client.py`
- [ ] Remove from `__init__.py` exports
- [ ] **Validate:** No import errors

### 4.3 Remove duplicate file watchers
- [ ] Delete `src/ingestion/file_watcher.py`
- [ ] Delete `src/ingestion/parallel_file_watcher.py`
- [ ] Keep only `async_file_watcher.py`
- [ ] **Validate:** File watching still works

### 4.4 Clean up root directory
- [ ] Delete `IMPLEMENTATION_SUMMARY.md`
- [ ] Delete `NEXT_STEPS.md`
- [ ] Delete `TROUBLESHOOTING.md` (move content to docs if needed)
- [ ] **Validate:** No references to deleted files

### 4.5 Consolidate scripts
- [ ] Move all `.bat` files to `scripts/windows/`
- [ ] Move all `.sh` files to `scripts/unix/`
- [ ] Update script references in docs
- [ ] **Validate:** Scripts work from new location

## Phase 5: Add Documentation

### 5.1 Add module docstrings
- [ ] Add docstrings to all `__init__.py` files
- [ ] Add module docstrings to all Python files
- [ ] Document exports with `__all__`
- [ ] **Validate:** `pydoc` generates docs without errors

### 5.2 Add function docstrings
- [ ] Add Google-style docstrings to all public functions
- [ ] Add docstrings to all class methods
- [ ] Include Args, Returns, Raises, Example sections
- [ ] **Validate:** Docstrings render correctly in IDE

### 5.3 Add inline comments
- [ ] Add comments to complex algorithms in semantic_chunker.py
- [ ] Add comments to RAG pipeline logic
- [ ] Comment state management in main.py
- [ ] **Validate:** Code review by peer

### 5.4 Update README.md
- [ ] Add comprehensive architecture section
- [ ] Document all API endpoints with curl examples
- [ ] Add performance tuning section
- [ ] Update quick start guide
- [ ] Add troubleshooting section
- [ ] **Validate:** README builds correctly (if using mdbook)

### 5.5 Create architecture documentation
- [ ] Create `docs/ARCHITECTURE.md` with system diagram
- [ ] Document RAG pipeline flow
- [ ] Document data ingestion flow
- [ ] Document service dependencies
- [ ] Add sequence diagrams for key operations
- [ ] **Validate:** Diagrams render correctly

### 5.6 Document environment variables
- [ ] Create `docs/CONFIGURATION.md`
- [ ] Document all environment variables
- [ ] Add default values and examples
- [ ] Document Docker-specific settings
- [ ] **Validate:** All env vars are documented

## Phase 6: Add Logging

### 6.1 Add API logging
- [ ] Add request/response logging middleware
- [ ] Log request ID, method, path, status code
- [ ] Log response time
- [ ] Add error logging with stack traces
- [ ] **Validate:** Check logs show all requests

### 6.2 Add service logging
- [ ] Add logging to LlamaIndexService operations
- [ ] Add logging to Neo4j operations
- [ ] Add logging to Qdrant operations
- [ ] Log operation latencies
- [ ] **Validate:** Logs show service calls

### 6.3 Add ingestion logging
- [ ] Log file ingestion start/end
- [ ] Log chunking statistics
- [ ] Log embedding generation
- [ ] Log vector storage operations
- [ ] **Validate:** Ingestion logs are complete

### 6.4 Add cache logging
- [ ] Log Redis cache hits/misses
- [ ] Log cache operation latencies
- [ ] Log cache size metrics
- [ ] **Validate:** Cache metrics in logs

## Phase 7: Improve Code Quality

### 7.1 Add type hints
- [ ] Add type hints to all function signatures
- [ ] Add return type hints
- [ ] Use Optional, Union, List, Dict appropriately
- [ ] Fix mypy errors
- [ ] **Validate:** `mypy --strict src/` passes

### 7.2 Add error handling
- [ ] Create custom exception classes
- [ ] Replace generic exceptions with specific ones
- [ ] Add try/except blocks where needed
- [ ] Add error context information
- [ ] **Validate:** Error messages are clear

### 7.3 Add validation
- [ ] Create `src/utils/validators.py`
- [ ] Add input validation for API endpoints
- [ ] Add configuration validation
- [ ] Add data validation in services
- [ ] **Validate:** Invalid inputs raise clear errors

### 7.4 Add constants
- [ ] Extract magic numbers to constants
- [ ] Create `src/utils/constants.py`
- [ ] Document constant meanings
- [ ] **Validate:** No magic numbers in code

## Phase 8: Testing and Validation

### 8.1 Run test suite
- [ ] Run `pytest tests/`
- [ ] Fix any failing tests
- [ ] Add tests for new routers
- [ ] **Validate:** All tests pass

### 8.2 Run linters
- [ ] Run `black --check src/`
- [ ] Run `ruff check src/`
- [ ] Run `mypy --strict src/`
- [ ] Fix all errors
- [ ] **Validate:** Zero linting errors

### 8.3 Test Docker deployment
- [ ] Build Docker image
- [ ] Start all services
- [ ] Check health endpoint
- [ ] Test ingestion
- [ ] Test RAG query
- [ ] **Validate:** Full stack works in Docker

### 8.4 Manual smoke testing
- [ ] Test all API endpoints via Swagger UI
- [ ] Ingest sample SQL file
- [ ] Execute RAG queries
- [ ] Check metrics endpoints
- [ ] Verify logging output
- [ ] **Validate:** No runtime errors

### 8.5 Update .gitignore
- [ ] Add patterns for new directories
- [ ] Remove patterns for deleted directories
- [ ] Ensure venv, data, logs are ignored
- [ ] **Validate:** `git status` is clean

## Phase 9: Documentation Organization

### 9.1 Create documentation directory structure
- [x] Create `docs/setup/` directory
- [x] Create `docs/architecture/` directory
- [x] Create `docs/api/` directory
- [x] Create `docs/guides/` directory
- [x] Create `docs/database/` directory
- [x] Create `docs/troubleshooting/` directory
- [x] **Validate:** All directories exist

### 9.2 Move architecture documentation
- [x] Move `ARCHITECTURE.md` from root to `docs/architecture/`
- [x] Keep newer version (372 lines) from root
- [x] Remove older version from `docs/ARCHITECTURE.md`
- [x] Move `LLAMAINDEX_RAG.md` to `docs/architecture/`
- [x] Move `IMPLEMENTATION_STATUS.md` to `docs/architecture/`
- [x] **Validate:** No duplicate ARCHITECTURE.md files

### 9.3 Move API documentation
- [x] Move `API_REFERENCE.md` from root to `docs/api/`
- [x] **Validate:** API_REFERENCE.md only in docs/api/

### 9.4 Organize setup documentation
- [x] Move `DOCKER_SETUP.md` to `docs/setup/`
- [x] Move `GETTING_STARTED.md` to `docs/setup/`
- [x] Move `LOCAL_SETUP_GUIDE.md` to `docs/setup/`
- [x] Move `DOCKER_TROUBLESHOOTING.md` to `docs/setup/`
- [x] Add deprecation notice to `LOCAL_SETUP_GUIDE.md`
- [x] **Validate:** All setup docs in docs/setup/

### 9.5 Organize guide documentation
- [x] Move `SQL_ORGANIZER_QUICKSTART.md` to `docs/guides/`
- [x] Move `HIERARCHICAL_ORGANIZATION_GUIDE.md` to `docs/guides/`
- [x] Move `FILE_WATCHER_GUIDE.md` to `docs/guides/`
- [x] Move `EXPORT_GUIDE.md` to `docs/guides/`
- [x] Move `ADVENTUREWORKS_GUIDE.md` to `docs/guides/`
- [x] **Validate:** All guides in docs/guides/

### 9.6 Organize database documentation
- [x] Move `QDRANT_SETUP.md` to `docs/database/`
- [x] Move `GREMLIN_SETUP.md` to `docs/database/`
- [x] **Validate:** Database docs in docs/database/

### 9.7 Organize troubleshooting documentation
- [x] Move `TROUBLESHOOTING.md` from root to `docs/troubleshooting/`
- [x] Move `IMPLEMENTATION_SUMMARY.md` from root to `docs/troubleshooting/`
- [x] Move `NEXT_STEPS.md` from root to `docs/troubleshooting/`
- [x] **Validate:** Troubleshooting docs organized

### 9.8 Update docs/README.md hub
- [x] Update all file paths in docs/README.md
- [x] Verify all links point to correct locations
- [x] Update directory structure illustration
- [x] Add new categories (troubleshooting/)
- [x] **Validate:** All links in docs/README.md work

### 9.9 Update root README.md
- [x] Update documentation links to point to docs/
- [x] Update architecture link to docs/architecture/ARCHITECTURE.md
- [x] Update API reference link to docs/api/API_REFERENCE.md
- [x] Keep docs/README.md as primary documentation hub
- [x] **Validate:** All README.md links work

### 9.10 Clean root directory
- [x] Verify only essential files remain in root:
  - README.md, CONTRIBUTING.md, CLEANUP_SUMMARY.md
  - .env.example, .gitignore, requirements*.txt
  - docker-compose*.yml, Dockerfile*
  - scripts/
- [x] **Validate:** Root directory is clean and organized

## Phase 10: Script Consolidation

### 10.1 Move deprecated startup scripts
- [x] Create `scripts/legacy/` directory
- [x] Move `start-local.bat` to `scripts/legacy/`
- [x] Move `start-simple.bat` to `scripts/legacy/`
- [x] Create `scripts/legacy/README.md` explaining deprecation
- [x] **Validate:** Deprecated scripts in scripts/legacy/

### 10.2 Add deprecation warnings to legacy scripts
- [x] Add deprecation warning to `scripts/legacy/start-local.bat`
- [x] Add deprecation warning to `scripts/legacy/start-simple.bat`
- [x] Warnings should recommend `start-docker.bat`
- [x] Warnings should require user confirmation
- [x] **Validate:** Warnings display when scripts run

### 10.3 Keep primary Docker scripts in root
- [x] Keep `start-docker.{bat,sh}` in root
- [x] Keep `stop-docker.{bat,sh}` in root
- [x] Keep `logs-docker.{bat,sh}` in root
- [x] Keep `check-docker.{bat,sh}` in root
- [x] **Validate:** Docker scripts easily accessible from root

### 10.4 Consolidate Docker Compose files
- [x] Rename `docker-compose.local.yml` to `docker-compose.yml`
- [x] Keep `docker-compose.prod.yml` as overlay
- [x] Keep `docker-compose.neo4j.yml` as optional
- [x] Remove unused Docker Compose files
- [x] Update scripts to use `docker-compose.yml`
- [x] **Validate:** Docker Compose works with new names

### 10.5 Update script documentation
- [x] Update README.md with Docker script usage
- [x] Update docs/setup/DOCKER_SETUP.md
- [x] Document legacy scripts in scripts/legacy/README.md
- [x] Document all utility scripts in scripts/README.md
- [x] **Validate:** All scripts documented

### 10.6 Verify cross-platform parity
- [x] Compare start-docker.bat and start-docker.sh
- [x] Compare stop-docker.bat and stop-docker.sh
- [x] Compare logs-docker.bat and logs-docker.sh
- [x] Compare check-docker.bat and check-docker.sh
- [x] Ensure feature parity
- [x] **Validate:** Both platforms have equivalent scripts

## Success Metrics

After completing all tasks:
- ✅ All tests pass
- ✅ Zero linting errors
- ✅ All files have docstrings
- ✅ No file > 500 lines
- ✅ Docker deployment works
- ✅ README is comprehensive
- ✅ All env vars documented
- ✅ Logging in every module
- ✅ Documentation organized by category
- ✅ No duplicate documentation files
- ✅ Root directory clean (< 15 files)
- ✅ Deprecated scripts moved to scripts/legacy/
- ✅ Docker Compose files consolidated
- ✅ All documentation links work
