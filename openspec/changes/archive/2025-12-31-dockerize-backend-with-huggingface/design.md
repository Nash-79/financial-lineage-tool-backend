# Design: Complete Docker Compose Backend with Ollama RAG Integration

## Context

The Financial Lineage Tool has partial Docker infrastructure:
- `docker-compose.local.yml` with Qdrant, Redis, API, and Jupyter
- `Dockerfile.local` for the API service
- `requirements-local.txt` with Ollama client
- Ollama integration in `main_local.py`

However, the Docker setup is incomplete:
- Not used as primary deployment method
- No RAG (Retrieval-Augmented Generation) capabilities
- No LlamaIndex integration for unified LLM operations
- Manual scripts still required
- Limited testing and validation

## Goals

1. **Docker-First Deployment**: Make `docker compose up` the recommended method
2. **RAG Integration**: Implement proper RAG pipeline with LlamaIndex + Ollama
3. **Complete Stack**: All services working together (API, Qdrant, Redis, Neo4j)
4. **Developer Experience**: Hot-reload, easy debugging, comprehensive docs
5. **Production Ready**: Health checks, resource limits, logging

## Non-Goals

- Replacing Ollama with cloud services (keep it local and free)
- Kubernetes deployment (Docker Compose sufficient)
- Containerizing Ollama itself (runs on host, accessed via network)
- Custom model training

## Decisions

### 1. Keep Existing Docker Compose Structure

**Decision**: Enhance `docker-compose.local.yml` rather than replace it

**Current Services**:
```yaml
services:
  qdrant:    # Vector database (already configured)
  redis:     # Caching (already configured)
  api:       # FastAPI app (already configured)
  jupyter:   # Notebooks (already configured)
```

**Enhancements**:
- Add health checks to all services
- Add Neo4j service (optional local instance)
- Improve volume configurations
- Add resource limits
- Enhanced logging

**Rationale**:
- Existing structure is sound
- Users may have customized it
- Incremental improvement safer than rewrite

### 2. Ollama + LlamaIndex Architecture

**Decision**: Integrate LlamaIndex with local Ollama for RAG

**Architecture**:
```python
LlamaIndex Framework
├── LLM: Ollama (host.docker.internal:11434)
│   ├── Model: llama3.1:8b
│   └── Use: Chat completions, reasoning
├── Embeddings: Ollama
│   ├── Model: nomic-embed-text
│   └── Use: Vector search (768 dimensions)
└── VectorStore: Qdrant
    ├── Host: qdrant:6333 (Docker service)
    └── Collections: code_chunks
```

**RAG Pipeline**:
```
1. Document Loading → Load SQL files
2. Chunking → Semantic chunker splits code
3. Embedding → Ollama generates 768d vectors
4. Indexing → LlamaIndex stores in Qdrant
5. Query → User question
6. Retrieval → LlamaIndex retrieves relevant chunks
7. Generation → Ollama generates answer with context
```

**Rationale**:
- **LlamaIndex benefits**:
  - Unified framework for RAG
  - Built-in document indexing
  - Query engines with context management
  - Automatic prompt construction
  - Observability and debugging tools
- **Ollama integration**:
  - Already installed and working
  - Free, no API costs
  - Works offline
  - Full control over models
  - Good performance with llama3.1:8b

**Alternatives Considered**:
- **LangChain**: More complex, heavier dependencies
- **Custom RAG**: Reinventing the wheel, more maintenance
- **HuggingFace**: Requires internet, API limits

### 3. Docker Networking for Ollama Access

**Decision**: Access Ollama on host via `host.docker.internal`

**Current Configuration** (already in docker-compose.local.yml):
```yaml
api:
  environment:
    - OLLAMA_HOST=http://host.docker.internal:11434
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

**Rationale**:
- Ollama runs on host (not containerized)
- `host.docker.internal` is Docker's way to access host from container
- Windows/Mac: Works out of the box
- Linux: Requires `extra_hosts` (already configured)

**Alternatives Considered**:
- Containerize Ollama: Too complex, GPU passthrough issues
- Network mode host: Breaks service isolation

### 4. LlamaIndex Document Indexing Strategy

**Decision**: Use LlamaIndex `VectorStoreIndex` with custom chunking

**Implementation**:
```python
# 1. Load documents
documents = load_sql_files(directory)

# 2. Chunk with existing semantic chunker
chunks = semantic_chunker.chunk_files(documents)

# 3. Convert to LlamaIndex documents
llama_docs = [Document(text=chunk.content, metadata=chunk.metadata)
              for chunk in chunks]

# 4. Create index with Qdrant vector store
vector_store = QdrantVectorStore(client=qdrant_client, collection_name="code_chunks")
index = VectorStoreIndex.from_documents(
    llama_docs,
    vector_store=vector_store,
    embed_model=OllamaEmbedding(model_name="nomic-embed-text", base_url=ollama_url)
)

# 5. Query with retrieval
query_engine = index.as_query_engine(
    similarity_top_k=5,
    llm=Ollama(model="llama3.1:8b", base_url=ollama_url)
)
response = query_engine.query("What is the lineage of customer_id?")
```

**Rationale**:
- Reuse existing semantic chunker (proven for SQL)
- LlamaIndex handles embedding and storage
- Query engine manages retrieval + generation
- Metadata preserved for filtering

### 5. Development and Production Configurations

**Decision**: Use compose file overrides for different environments

**Files**:
```
docker-compose.local.yml       # Base (development default)
docker-compose.override.yml    # User customizations (gitignored)
docker-compose.prod.yml        # Production overrides
docker-compose.neo4j.yml       # Optional local Neo4j
```

**Development** (default):
```yaml
api:
  volumes:
    - ./src:/app/src:ro      # Hot-reload
    - ./config:/app/config:ro
  command: uvicorn src.api.main_local:app --reload --host 0.0.0.0
```

**Production**:
```yaml
api:
  restart: always
  deploy:
    resources:
      limits:
        memory: 2G
        cpus: '1.0'
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

**Rationale**:
- Compose file merging is Docker's native way
- Development friendly by default
- Easy to add production optimizations
- User customizations in override.yml

### 6. Neo4j Integration

**Decision**: Support both cloud and local Neo4j via environment variables

**Configuration**:
```yaml
# Optional local Neo4j service
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"  # Browser
    - "7687:7687"  # Bolt
  environment:
    - NEO4J_AUTH=neo4j/password
  volumes:
    - neo4j-data:/data
```

**Environment Variables**:
```bash
# Cloud Neo4j (default from .env)
NEO4J_URI=neo4j+s://66e1cb8c.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...

# Local Neo4j (alternative)
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

**Usage**:
```bash
# Cloud Neo4j (default)
docker compose up

# Local Neo4j
docker compose -f docker-compose.local.yml -f docker-compose.neo4j.yml up
```

**Rationale**:
- Support both deployment scenarios
- Cloud is default (free tier, no setup)
- Local available for offline/testing
- Environment variable driven (flexible)

## Technical Specifications

### LlamaIndex Integration

**Dependencies to Add** (`requirements-local.txt`):
```txt
llama-index>=0.10.0
llama-index-embeddings-ollama>=0.1.0
llama-index-llms-ollama>=0.1.0
llama-index-vector-stores-qdrant>=0.2.0
```

**Service Layer**:
```python
class LlamaIndexService:
    def __init__(self, ollama_url, qdrant_client):
        self.llm = Ollama(model="llama3.1:8b", base_url=ollama_url)
        self.embed_model = OllamaEmbedding(
            model_name="nomic-embed-text",
            base_url=ollama_url
        )
        self.vector_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name="code_chunks"
        )

    def index_documents(self, documents):
        """Index documents with embeddings."""
        index = VectorStoreIndex.from_documents(
            documents,
            vector_store=self.vector_store,
            embed_model=self.embed_model,
            show_progress=True
        )
        return index

    def create_query_engine(self, index):
        """Create RAG query engine."""
        return index.as_query_engine(
            similarity_top_k=5,
            llm=self.llm,
            response_mode="compact"  # or "tree_summarize"
        )
```

### Docker Compose Enhancements

**Health Checks**:
```yaml
qdrant:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 10s

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3

api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
  depends_on:
    qdrant:
      condition: service_healthy
    redis:
      condition: service_healthy
```

**Resource Limits**:
```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 2G
      reservations:
        memory: 512M

qdrant:
  deploy:
    resources:
      limits:
        cpus: '0.5'
        memory: 1G

redis:
  deploy:
    resources:
      limits:
        memory: 256M
```

### Admin Restart Endpoint

**Decision**: Provide `/admin/restart` endpoint for frontend-triggered container restart

**Implementation**:
```python
import os
import signal

@app.post("/admin/restart")
async def restart_server():
    """
    Trigger graceful shutdown - Docker restart policy will bring it back.

    This endpoint allows the frontend UI to restart the backend container
    for applying configuration changes or recovering from issues.
    """
    # TODO: Add authentication/authorization
    # TODO: Log restart attempt
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "restarting"}
```

**Docker Configuration**:
```yaml
api:
  restart: unless-stopped  # or "always"
  stop_grace_period: 30s   # Allow 30s for graceful shutdown
```

**Graceful Shutdown Handler**:
```python
import signal
import asyncio

async def graceful_shutdown(signal, loop):
    """Handle graceful shutdown on SIGTERM."""
    print(f"Received exit signal {signal.name}...")

    # Close database connections
    if state.graph:
        state.graph.close()

    # Close HTTP clients
    if state.ollama:
        await state.ollama.close()
    if state.qdrant:
        await state.qdrant.close()

    # Stop accepting new requests
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

# Register signal handlers
loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(graceful_shutdown(s, loop)))
```

**Rationale**:
- Frontend needs way to restart backend (e.g., after config changes)
- Docker restart policy ensures automatic recovery
- SIGTERM allows graceful shutdown (complete requests, close connections)
- 30s timeout prevents hung shutdowns

**Security Considerations**:
- Endpoint should require admin authentication (API key or JWT)
- Rate limiting to prevent abuse (max 1 restart per minute)
- Log all restart attempts with source IP
- Consider feature flag to disable in production

### Startup Scripts Enhancement

**start-docker.bat** (new primary method):
```batch
@echo off
echo Starting Financial Lineage Tool with Docker...
docker compose -f docker-compose.local.yml up -d
echo.
echo Services starting. Check status with: docker compose ps
echo View logs: docker compose logs -f
echo Stop: docker compose down
```

**start-local.bat** (deprecated, kept for compatibility):
```batch
@echo off
echo WARNING: Manual startup is deprecated. Use start-docker.bat instead.
echo Press Ctrl+C to cancel or wait 5 seconds to continue...
timeout /t 5
REM ... existing manual startup code ...
```

## Migration Plan

### Phase 1: Add LlamaIndex Integration (No Breaking Changes)
1. Add LlamaIndex dependencies to requirements-local.txt
2. Create LlamaIndexService alongside existing code
3. Add feature flag to switch between old/new RAG
4. Test both implementations in parallel
5. Update documentation with LlamaIndex option

### Phase 2: Enhance Docker Compose
1. Add health checks to docker-compose.local.yml
2. Add resource limits
3. Create docker-compose.prod.yml
4. Create docker-compose.neo4j.yml
5. Test all combinations

### Phase 3: Make Docker Primary (Gentle Breaking Change)
1. Update README to recommend Docker first
2. Create start-docker.bat as primary script
3. Mark manual scripts as deprecated
4. Keep manual scripts working for 2 releases
5. Update all documentation

### Phase 4: Switch to LlamaIndex RAG (Internal Change)
1. Make LlamaIndex the default RAG implementation
2. Remove old RAG code
3. Update all endpoints to use new service
4. Ensure backward compatibility for API responses

### Rollback Strategy
- Keep old code until Phase 4
- Feature flags allow instant rollback
- Docker optional until Phase 3
- Git tags for each phase

## Risks / Trade-offs

### Risk: Ollama Availability
**Impact**: Docker container can't reach Ollama on host
**Mitigation**:
- Clear error messages on startup
- Health check detects Ollama connection
- Documentation for Ollama setup
- Test `host.docker.internal` connectivity

### Risk: Docker Learning Curve
**Impact**: New users unfamiliar with Docker
**Mitigation**:
- Comprehensive quick-start guide
- Video walkthrough (future)
- Keep manual method working
- Pre-flight check script

### Risk: Volume Permissions
**Impact**: Permission issues with bind mounts on Linux
**Mitigation**:
- Document UID/GID mapping
- Use named volumes for data
- Read-only mounts where possible

### Trade-off: Docker Overhead
**Impact**: Slightly higher resource usage than bare metal
**Mitigation**:
- Resource limits prevent runaway usage
- Still lighter than full VMs
- Benefits outweigh costs

### Trade-off: LlamaIndex Abstraction
**Impact**: Less control vs custom RAG implementation
**Mitigation**:
- LlamaIndex is extensible
- Can drop down to lower level APIs
- Active development and community
- Simpler maintenance

## Open Questions

1. **Should we deprecate Jupyter service?**
   - Keep it (useful for exploration)
   - Update to use LlamaIndex in notebooks

2. **How to handle Ollama model updates?**
   - Document model pull process
   - Add startup check for required models
   - Consider model version pinning

3. **Should we add pgAdmin for Neo4j?**
   - Add neo4j browser (already included in container)
   - Document connection from host

4. **Redis usage?**
   - Currently minimal usage
   - Plan: Cache LlamaIndex embeddings
   - Plan: Cache query results

## Success Metrics

- **Setup Time**: <5 minutes with Docker (vs 20+ manual)
- **Developer Onboarding**: Single command (`docker compose up`)
- **RAG Quality**: LlamaIndex improves answer relevance by 30%+
- **Response Time**: <2s for queries (with RAG)
- **Reliability**: 99%+ uptime for containerized stack
- **Resource Usage**: <4GB RAM total (all containers)
