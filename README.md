# Financial Data Lineage Tool (Backend)

An AI-powered solution for SQL database analysis, knowledge graph creation, and data lineage visualization with **local-first LLMs** and **containerized deployment**.

> **Note**: The frontend web application is maintained in a separate repository: `financial-lineage-tool-frontend`

## 🚀 Quick Start (Docker - Recommended)

**Prerequisites:**
- Docker Desktop 20.10+
- Ollama (for LLM features)

```bash
# 1. Validate your setup
check-docker.bat          # Windows
./check-docker.sh         # Unix/Linux/macOS

# 2. Start all services
start-docker.bat          # Windows
./start-docker.sh         # Unix/Linux/macOS

# 3. Access the API
# API:     http://localhost:8000
# Docs:    http://localhost:8000/docs
# Health:  http://localhost:8000/health
```

That's it! All services (API, Qdrant, Redis) are now running in Docker.

## 📚 Documentation

**[📖 Enter Documentation Hub](docs/README.md)** - Complete documentation index

**Quick Links:**
- **[🐳 Docker Setup](docs/setup/DOCKER_SETUP.md)**: Recommended deployment method
- **[🏗️ Architecture](docs/architecture/ARCHITECTURE.md)**: System architecture overview
- **[📡 API Reference](docs/api/API_REFERENCE.md)**: Complete API endpoint documentation
- **[🤖 LlamaIndex RAG](docs/architecture/LLAMAINDEX_RAG.md)**: RAG pipeline details
- **[🔧 Contributing](CONTRIBUTING.md)**: Developer guidelines

## 🏗️ Architecture

### Services

| Service | Technology | Purpose | Port |
|---------|-----------|---------|------|
| **API** | FastAPI | REST API & RAG endpoints | 8000 |
| **Ollama** | Llama 3.1 8B | Local LLM (runs on host) | 11434 |
| **Qdrant** | Vector DB | Embeddings storage | 6333 |
| **Neo4j** | Graph DB | Knowledge graph | 7687 |
| **Redis** | Cache | Query & embedding cache | 6379 |

### Tech Stack

- **LLM**: Ollama (llama3.1:8b, nomic-embed-text)
- **RAG**: LlamaIndex framework
- **Vector DB**: Qdrant (768-dimensional embeddings)
- **Graph DB**: Neo4j (Cypher queries)
- **API**: FastAPI with async/await
- **Deployment**: Docker Compose

## 📂 Data Folder Structure

The tool uses a hierarchical data organization by database:

```
data/
└── {database-name}/
    ├── raw/              # Original SQL files
    ├── separated/        # Separated SQL objects (tables, views, etc.)
    ├── embeddings/       # Vector embeddings
    ├── graph/            # Knowledge graph exports
    └── metadata/         # Processing logs and stats
```

See [data/README.md](data/README.md) for complete documentation.

## 🔗 API Endpoints

### Chat Endpoints
- `POST /api/chat/deep` - Deep analysis with comprehensive lineage
- `POST /api/chat/semantic` - Semantic search queries
- `POST /api/chat/graph` - Graph-based relationship queries
- `POST /api/chat/text` - Simple text chat

### Lineage & Data
- `GET /api/v1/lineage/nodes` - All graph nodes
- `GET /api/v1/lineage/edges` - All relationships
- `GET /api/v1/lineage/search` - Search lineage
- `GET /api/v1/files/recent` - Recent files
- `GET /api/database/schemas` - Database schemas

### Monitoring
- `GET /health` - Service health check
- `GET /api/v1/rag/status` - RAG metrics
- `POST /admin/restart` - Restart container
- `WS /api/v1/ws/dashboard` - Real-time dashboard stats

**Full API docs**: http://localhost:8000/docs

## 🛠️ Development

### Docker Commands

```bash
# Start services
start-docker.bat / ./start-docker.sh

# View logs
logs-docker.bat / ./logs-docker.sh

# Stop services
stop-docker.bat / ./stop-docker.sh

# Restart API only
docker compose -f docker-compose.local.yml restart api
```

### Manual Setup (Deprecated)

For manual setup without Docker, see [docs/LOCAL_SETUP_GUIDE.md](docs/LOCAL_SETUP_GUIDE.md).

**Note**: Docker Compose is now the recommended deployment method.

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# Run integration tests (requires running services)
pytest tests/ -v -m integration

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 📦 Environment Variables

Key configuration (see [.env.example](.env.example) for full list):

```bash
# LLM Configuration
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text

# LlamaIndex
USE_LLAMAINDEX=true
SIMILARITY_TOP_K=5

# Services (Docker auto-configures these)
QDRANT_HOST=qdrant
REDIS_HOST=redis
NEO4J_URI=your-neo4j-uri
```

## License

Proprietary - Internal Use Only
