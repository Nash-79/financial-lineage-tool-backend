# Project Context

## Purpose
Financial Lineage Tool - A RAG-powered backend service for analyzing SQL database schemas, tracking data lineage, and providing intelligent semantic search over database artifacts using LlamaIndex and local Ollama LLMs.

## Tech Stack
- **Backend**: Python 3.11, FastAPI, Uvicorn
- **LLM/RAG**: LlamaIndex, Ollama (llama3.1:8b, nomic-embed-text)
- **Vector Database**: Qdrant (768-dimensional embeddings)
- **Graph Database**: Neo4j (cloud-hosted)
- **Cache**: Redis
- **Containerization**: Docker, Docker Compose
- **SQL Parsing**: sqlglot
- **Testing**: pytest, pytest-asyncio
- **Code Quality**: black, ruff

## Project Conventions

### Code Style
- Python code formatted with `black` (line length: 88)
- Linting with `ruff`
- Type hints required for function signatures
- Async/await for I/O operations
- Pydantic models for API request/response validation

### Architecture Patterns
- Multi-service Docker architecture with health checks
- RAG pipeline: Document ingestion → Embedding → Vector search → LLM generation
- Feature flags for gradual rollout (USE_LLAMAINDEX)
- Repository pattern for database access
- Service layer for business logic
- RESTful API design with OpenAPI/Swagger docs

### Testing Strategy
- Unit tests with pytest
- Async tests with pytest-asyncio
- Integration tests for API endpoints
- Test coverage for critical RAG pipeline components
- Docker-based testing environment

### Git Workflow
- Main branch: `main`
- Feature branches with descriptive names
- OpenSpec-driven development for major changes
- Commit messages with co-authorship for AI assistance

## Domain Context
- SQL schema analysis and lineage tracking
- Semantic search over database artifacts (tables, views, procedures, functions)
- Knowledge graph construction from SQL metadata
- RAG-powered natural language queries about database structure

## Important Constraints
- Ollama must run on host machine (not in Docker)
- Docker containers access Ollama via `host.docker.internal`
- Embeddings are 768-dimensional (nomic-embed-text)
- Neo4j uses cloud instance (Aura)
- Resource limits: API (2GB RAM, 2 CPUs), Qdrant (1GB RAM)

## External Dependencies
- **Ollama**: http://localhost:11434 (required)
  - Models: llama3.1:8b (4.7GB), nomic-embed-text (274MB)
- **Neo4j Aura**: neo4j+s://66e1cb8c.databases.neo4j.io
- **Qdrant**: In-memory vector storage, optional persistence
- **Redis**: Caching layer for embeddings and queries
