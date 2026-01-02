# Financial Lineage Tool - Local Setup (100% FREE)

This guide will help you run the Financial Lineage Tool locally using Ollama instead of paid cloud services.

## Current Status: RUNNING ✓

Your local instance is now running! All services are started and ready to use.

## Services Running

| Service | Status | URL | Purpose |
|---------|--------|-----|---------|
| API Server | ✓ Running | http://localhost:8000 | Main application API |
| Ollama | ✓ Running | http://localhost:11434 | Local LLM (llama3.1:8b) |
| Qdrant | ✓ Running | http://localhost:6333 | Vector database |
| Gremlin Server | ✓ Running | http://localhost:8182 | Graph database |
| Redis | ✓ Running | http://localhost:6379 | Caching (optional) |

## Quick Start

### 1. Access the API Documentation
Open in your browser: http://localhost:8000/docs

This provides an interactive Swagger UI where you can test all endpoints.

### 2. Test the API

Run the test script:
```bash
python test_local_api.py
```

### 3. Example API Usage

#### Query Lineage (using local Ollama):
```bash
curl -X POST "http://localhost:8000/api/v1/lineage/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is data lineage?",
    "include_validation": false
  }'
```

#### Check Health:
```bash
curl http://localhost:8000/health
```

#### List Ollama Models:
```bash
curl http://localhost:11434/api/tags
```

## Architecture

### Local Stack (NO CLOUD COSTS)
- **LLM**: Ollama with llama3.1:8b (4.9 GB model)
- **Embeddings**: nomic-embed-text (274 MB model)
- **Vector DB**: Qdrant (open source)
- **Graph DB**: NetworkX (in-memory) + Gremlin Server (optional)
- **Web Framework**: FastAPI

### Configuration Files
- `.env` - Environment variables (already configured)
- `docker-compose.local.yml` - Docker services
- `src/api/main_local.py` - Local API implementation

## Managing Services

### Stop Services
```bash
# Stop the API server
# Press Ctrl+C in the terminal where it's running

# Stop Docker services
docker compose -f docker-compose.local.yml down
```

### Start Services
```bash
# Start Docker services
docker compose -f docker-compose.local.yml up -d gremlin-server qdrant redis

# Start API server
python src/api/main_local.py
```

### Restart Everything
```bash
# Stop Docker services
docker compose -f docker-compose.local.yml down

# Start Docker services
docker compose -f docker-compose.local.yml up -d gremlin-server qdrant redis

# Start API server
python src/api/main_local.py
```

## Available Endpoints

### Lineage Queries
- `POST /api/v1/lineage/query` - Natural language lineage queries
- `POST /api/v1/lineage/column` - Column-level lineage
- `GET /api/v1/lineage/column/{column_name}` - Get column lineage
- `GET /api/v1/lineage/table/{table_name}` - Get table lineage

### Ingestion
- `POST /api/v1/ingest/repository` - Ingest code repository
- `GET /api/v1/ingest/status/{job_id}` - Check ingestion status

### Graph Operations
- `POST /api/v1/graph/traverse` - Traverse the knowledge graph
- `GET /api/v1/graph/entity/{entity_id}` - Get entity details

### Search
- `GET /api/v1/search/code` - Search code corpus

### System
- `GET /health` - Health check
- `GET /api/v1/models` - List available Ollama models

## Data Ingestion Example

To ingest a code repository for lineage analysis:

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/ingest/repository",
    json={
        "repo_url": "https://github.com/your-org/your-repo",
        "branch": "main"
    }
)

job_id = response.json()["job_id"]
print(f"Ingestion started: {job_id}")
```

## Performance Notes

### Model Performance
- **llama3.1:8b**: Good balance of quality and speed for lineage queries
- **Response time**: 5-30 seconds depending on query complexity
- **Resource usage**: ~8GB RAM for models + services

### Upgrading Models
If you have a more powerful machine, you can use larger models:

```bash
# Pull a larger model
ollama pull llama3.1:70b

# Update .env file
LLM_MODEL=llama3.1:70b
```

## Troubleshooting

### API Server Won't Start
1. Check if port 8000 is already in use:
   ```bash
   netstat -ano | findstr :8000
   ```
2. Make sure all dependencies are installed:
   ```bash
   pip install -r requirements-local.txt
   ```

### Ollama Not Responding
1. Check if Ollama is running:
   ```bash
   ollama list
   ```
2. Restart Ollama service
3. Verify models are downloaded:
   ```bash
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```

### Docker Services Won't Start
1. Check Docker Desktop is running
2. View logs:
   ```bash
   docker compose -f docker-compose.local.yml logs
   ```
3. Remove old containers:
   ```bash
   docker compose -f docker-compose.local.yml down -v
   docker compose -f docker-compose.local.yml up -d
   ```

### Out of Memory
1. Close other applications
2. Use a smaller model (llama3.1:7b instead of 8b)
3. Reduce Docker memory limits in docker-compose.local.yml

## Cost Comparison

| Service | Cloud (Azure) | Local (Ollama) |
|---------|---------------|----------------|
| LLM API | $0.03-0.06/1K tokens | **$0.00** |
| Embeddings | $0.0001/1K tokens | **$0.00** |
| Vector DB | $0.40/hour | **$0.00** |
| Graph DB | $0.60/hour | **$0.00** |
| **Monthly (moderate use)** | **~$500-1000** | **$0.00** |

## Next Steps

1. **Ingest your code**: Use the `/api/v1/ingest/repository` endpoint
2. **Query lineage**: Use the `/api/v1/lineage/query` endpoint
3. **Explore the graph**: Use the graph traversal endpoints
4. **Build your app**: Use the API to build custom lineage tools

## Development Tips

- The in-memory graph is stored in `./data/lineage_graph.pkl`
- Vector embeddings are stored in Qdrant at `./qdrant-data/`
- Logs are output to the console where you started the API server
- Use the `/docs` endpoint for interactive API testing

## Environment Variables

All configuration is in the `.env` file:

```bash
# Ollama settings
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text

# Database settings
QDRANT_HOST=localhost
QDRANT_PORT=6333
GREMLIN_HOST=localhost
GREMLIN_PORT=8182

# Storage
STORAGE_PATH=./data
```

## Support

- Ollama Documentation: https://ollama.ai/
- Qdrant Documentation: https://qdrant.tech/documentation/
- FastAPI Documentation: https://fastapi.tiangolo.com/

---

**You are now running the Financial Lineage Tool completely locally with NO cloud costs!**
