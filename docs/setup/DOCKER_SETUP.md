# Docker Setup Guide

Complete guide for deploying the Financial Lineage Tool with Docker Compose.

## Prerequisites

### Required
- **Docker Desktop 20.10+** ([Download](https://www.docker.com/products/docker-desktop))
- **4GB+ RAM** available for containers
- **5GB+ disk space**

### Recommended for LLM Features
- **Ollama** ([Download](https://ollama.ai))
  - Model: `llama3.1:8b` (4.7GB)
  - Embeddings: `nomic-embed-text` (274MB)

---

## Quick Start

### 1. Validate Installation

```bash
# Windows
check-docker.bat

# Unix/Linux/macOS
./check-docker.sh
```

This script checks:
- ✅ Docker installed and running
- ✅ Docker Compose available
- ✅ Ollama installed and running
- ✅ Required models downloaded
- ✅ System resources

### 2. Start Services

```bash
# Windows
start-docker.bat

# Unix/Linux/macOS
./start-docker.sh
```

**What it does:**
1. Checks Docker and Ollama status
2. Starts all containers (`docker compose up -d --build`)
3. Waits for health checks to pass
4. Shows service URLs

### 3. Verify Services

```bash
# Check health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs  # macOS
start http://localhost:8000/docs # Windows
```

---

## Services Overview

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **API** | `lineage-api` | 8000 | FastAPI REST API |
| **Qdrant** | `qdrant` | 6333 | Vector embeddings |
| **Redis** | `redis` | 6379 | Caching |
| **Ollama** | host | 11434 | LLM (runs on host) |
| **Neo4j** | cloud/local | 7687 | Knowledge graph |

---

## Configuration

### Environment Variables

Create/edit `.env` file:

```bash
# For Docker (automatically configured)
OLLAMA_HOST=http://host.docker.internal:11434
QDRANT_HOST=qdrant
REDIS_HOST=redis

# For local development (override if needed)
# OLLAMA_HOST=http://localhost:11434
# QDRANT_HOST=localhost
# REDIS_HOST=localhost

# LlamaIndex
USE_LLAMAINDEX=true
SIMILARITY_TOP_K=5

# Neo4j (use cloud or local)
NEO4J_URI=your-neo4j-uri
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
```

### Docker Compose Files

| File | Purpose | Usage |
|------|---------|-------|
| `docker-compose.local.yml` | Base configuration | Development |
| `docker-compose.prod.yml` | Production overrides | Production |
| `docker-compose.neo4j.yml` | Local Neo4j | Optional |

**Production:**
```bash
docker compose -f docker-compose.local.yml -f docker-compose.prod.yml up -d
```

**With local Neo4j:**
```bash
docker compose -f docker-compose.local.yml -f docker-compose.neo4j.yml up -d
```

---

## Management

### View Logs

```bash
# All services
logs-docker.bat / ./logs-docker.sh

# Specific service
docker compose -f docker-compose.local.yml logs -f api
```

### Restart Services

```bash
# All services
docker compose -f docker-compose.local.yml restart

# API only
docker compose -f docker-compose.local.yml restart api

# Via API (graceful)
curl -X POST http://localhost:8000/admin/restart
```

### Stop Services

```bash
# Stop containers (keep data)
stop-docker.bat / ./stop-docker.sh

# Stop and remove volumes (delete data)
docker compose -f docker-compose.local.yml down -v
```

### Rebuild Containers

```bash
# Rebuild after code changes
docker compose -f docker-compose.local.yml up -d --build

# Force rebuild
docker compose -f docker-compose.local.yml build --no-cache
```

---

## Health Checks

### Built-in Health Checks

Each service has health checks configured:

**Qdrant:**
```yaml
test: ["CMD", "wget", "--spider", "http://localhost:6333/health"]
interval: 10s
```

**Redis:**
```yaml
test: ["CMD", "redis-cli", "ping"]
interval: 10s
```

**API:**
```yaml
test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
interval: 30s
start_period: 40s
```

### Check Status

```bash
# Container status
docker compose -f docker-compose.local.yml ps

# API health endpoint
curl http://localhost:8000/health | jq

# Expected response:
{
  "status": "healthy",
  "services": {
    "api": "up",
    "ollama": "up",
    "qdrant": "up",
    "neo4j": "up",
    "llamaindex": "healthy",
    "rag_mode": "llamaindex"
  }
}
```

---

## Troubleshooting

### Ollama Not Accessible

**Symptom:** API logs show Ollama connection errors

**Solution:**
```bash
# Windows: Ensure Ollama is running
ollama list

# Check if Docker can reach host
docker compose -f docker-compose.local.yml exec api curl http://host.docker.internal:11434/api/tags
```

### Port Already in Use

**Symptom:** `Error: port 8000 already allocated`

**Solution:**
```bash
# Find process using port
# Windows:
netstat -ano | findstr :8000
taskkill /PID <process_id> /F

# Unix/Linux:
lsof -i :8000
kill -9 <process_id>
```

### Container Keeps Restarting

**Symptom:** API container in restart loop

**Solution:**
```bash
# Check logs
docker compose -f docker-compose.local.yml logs api

# Common issues:
# - Ollama not accessible → Check OLLAMA_HOST
# - Neo4j connection failed → Check NEO4J_URI
# - Missing dependencies → Rebuild container
```

### Out of Memory

**Symptom:** Container killed (exit code 137)

**Solution:**
```bash
# Increase Docker memory allocation
# Docker Desktop → Settings → Resources → Memory: 8GB

# Or reduce resource limits in docker-compose.local.yml
```

---

## Data Persistence

### Volumes

Docker volumes persist data across restarts:

```yaml
volumes:
  qdrant-data:     # Vector embeddings
  redis-data:      # Cache
  neo4j-data:      # Graph (if using local Neo4j)
```

**Backup volumes:**
```bash
docker run --rm -v qdrant-data:/data -v $(pwd):/backup alpine tar czf /backup/qdrant-backup.tar.gz /data
```

**Restore volumes:**
```bash
docker run --rm -v qdrant-data:/data -v $(pwd):/backup alpine tar xzf /backup/qdrant-backup.tar.gz -C /
```

---

## Production Deployment

### Using docker-compose.prod.yml

```bash
docker compose -f docker-compose.local.yml -f docker-compose.prod.yml up -d
```

**Changes in production:**
- ✅ 4 uvicorn workers
- ✅ Always restart policy
- ✅ Higher resource limits (4 CPUs, 4GB)
- ✅ Extended logging retention
- ✅ Redis LRU eviction

### Security Considerations

**TODO (before production):**
- [ ] Add authentication to `/admin/restart`
- [ ] Configure rate limiting
- [ ] Set up HTTPS/SSL
- [ ] Use secrets management (not `.env`)
- [ ] Configure firewall rules
- [ ] Enable audit logging

---

## Performance Tuning

### Resource Limits

Edit `docker-compose.local.yml`:

```yaml
api:
  deploy:
    resources:
      limits:
        memory: 4G      # Increase if needed
        cpus: '4.0'     # Match your CPU cores
```

### Redis Caching

```bash
# Configure in .env
EMBEDDING_CACHE_TTL=86400  # 24 hours
QUERY_CACHE_TTL=3600       # 1 hour
```

### Qdrant Optimization

```yaml
qdrant:
  environment:
    - QDRANT__SERVICE__GRPC_PORT=6334
    - QDRANT__STORAGE__STORAGE_PATH=/qdrant/storage
```

---

## Next Steps

- ✅ [LlamaIndex RAG Guide](LLAMAINDEX_RAG.md)
- ✅ [API Documentation](http://localhost:8000/docs)
- ✅ [Architecture Overview](ARCHITECTURE.md)
