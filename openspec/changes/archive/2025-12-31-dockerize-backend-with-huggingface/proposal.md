# Change: Complete Docker Compose Backend with Ollama RAG Integration

## Why

The backend has existing Docker infrastructure (`docker-compose.local.yml`, `Dockerfile.local`) but:
- Docker services are not fully integrated or tested
- Manual startup scripts still required alongside Docker
- Ollama integration exists but lacks RAG capabilities
- No unified LLM framework for embeddings, chat, and retrieval
- Docker setup is not the primary/recommended deployment method

The existing `docker-compose.local.yml` already has:
- Qdrant vector database
- Redis caching
- API service with Dockerfile.local
- Proper networking and volumes

We need to:
- Make Docker Compose the primary deployment method
- Integrate LlamaIndex with local Ollama for RAG pipeline
- Ensure all services work together seamlessly
- Add comprehensive testing and validation
- Complete the containerization journey

## What Changes

- Enhance existing Docker Compose setup with production readiness
- Integrate LlamaIndex framework with local Ollama for RAG
- Add LlamaIndex document indexing and query engine
- Implement proper RAG pipeline (Retrieval-Augmented Generation)
- Implement complete API endpoints for frontend integration:
  - Chat endpoints: `/api/chat/deep`, `/api/chat/semantic`, `/api/chat/graph`, `/api/chat/text`
  - Lineage endpoints: `/api/lineage/nodes`, `/api/lineage/edges`, `/api/lineage/search`, `/api/lineage/node/{id}`
  - Data endpoints: `/api/files`, `/api/files/recent`, `/api/files/search`, `/api/files/stats`
  - Database endpoint: `/api/database/schemas`
  - System endpoints: `/api/stats`, `/api/activity/recent`, `/api/v1/rag/status`
  - Admin endpoint: `/admin/restart`
- Implement graceful shutdown handlers for Docker restarts
- Add Neo4j to Docker Compose (optional local instance)
- Enhance health checks and service dependencies
- Add development and production compose configurations
- Configure Docker restart policies and shutdown timeouts
- Update startup scripts to use Docker as default
- Add comprehensive testing suite
- Improve documentation for Docker deployment

## Impact

### Affected Specs
- `deployment` (new) - Docker Compose orchestration and containerization
- `llm-service` (new) - Ollama + LlamaIndex RAG integration
- `api-endpoints` (new) - Complete API endpoint specification for frontend

### Affected Code
- `src/api/main_local.py` - Integrate LlamaIndex RAG pipeline
- `src/knowledge_graph/entity_extractor.py` - Use LlamaIndex for extraction
- `src/ingestion/` - Add LlamaIndex document indexing
- `config/settings.py` - Add LlamaIndex configuration
- `docker-compose.local.yml` - Enhance existing configuration
- `Dockerfile.local` - Update for production readiness
- `.env.example` - Document all environment variables
- `requirements-local.txt` - Add LlamaIndex dependencies
- `start-local.bat` - Make Docker Compose primary method
- `README.md` - Update with Docker-first approach

### Migration Path
1. Existing Ollama installation remains (runs on host)
2. Docker Compose becomes the recommended deployment method
3. Manual startup scripts marked as deprecated but still available
4. Existing Neo4j cloud instance works with Docker setup
5. Qdrant data migrates to Docker volumes
6. No breaking API changes

### Breaking Changes
- **BREAKING**: Docker required for primary deployment method
- **BREAKING**: Python 3.11+ required (current Dockerfile uses 3.11)

### Non-Breaking
- Ollama remains on host (accessed via host.docker.internal)
- Neo4j connection unchanged (cloud or local)
- Qdrant API compatible
- FastAPI endpoints unchanged
- Existing data formats compatible
- Manual startup still works (deprecated)
