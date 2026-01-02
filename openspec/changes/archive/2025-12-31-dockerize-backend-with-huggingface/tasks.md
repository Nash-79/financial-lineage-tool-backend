# Implementation Tasks

## 1. Docker Compose Enhancement

- [ ] 1.1 Add health checks to all services in docker-compose.local.yml
- [ ] 1.2 Add depends_on with service_healthy conditions
- [ ] 1.3 Add resource limits (CPU, memory) to all services
- [ ] 1.4 Add restart policy (unless-stopped or always) to API service
- [ ] 1.5 Configure graceful shutdown timeout (30 seconds) for API
- [ ] 1.6 Create docker-compose.prod.yml with production overrides
- [ ] 1.7 Create docker-compose.neo4j.yml for optional local Neo4j
- [ ] 1.8 Add logging configuration (json-file driver with rotation)
- [ ] 1.9 Update Dockerfile.local with health check and optimization

## 2. LlamaIndex Integration

- [ ] 2.1 Add LlamaIndex dependencies to requirements-local.txt
- [ ] 2.2 Create src/llm/llamaindex_service.py service class
- [ ] 2.3 Implement Ollama LLM integration with LlamaIndex
- [ ] 2.4 Implement Ollama embeddings integration with LlamaIndex
- [ ] 2.5 Implement Qdrant vector store integration with LlamaIndex
- [ ] 2.6 Create document indexing pipeline
- [ ] 2.7 Create query engine with RAG capabilities
- [ ] 2.8 Add metadata filtering for lineage queries

## 3. RAG Pipeline Implementation

- [ ] 3.1 Integrate semantic chunker with LlamaIndex documents
- [ ] 3.2 Implement batch document indexing
- [ ] 3.3 Create query engine with context retrieval
- [ ] 3.4 Add prompt templates for lineage questions
- [ ] 3.5 Implement response synthesis with citations
- [ ] 3.6 Add caching for embeddings (Redis integration)
- [ ] 3.7 Add query optimization (similarity thresholds)

## 4. API Endpoint Implementation

### 4.1 Chat Endpoints
- [ ] 4.1.1 Implement POST /api/chat/deep for deep analysis queries
- [ ] 4.1.2 Implement POST /api/chat/semantic for semantic search queries
- [ ] 4.1.3 Implement POST /api/chat/graph for graph-based queries
- [ ] 4.1.4 Implement POST /api/chat/text for simple text queries
- [ ] 4.1.5 Add request/response models for chat endpoints
- [ ] 4.1.6 Integrate chat endpoints with LlamaIndex RAG pipeline

### 4.2 Lineage Endpoints
- [ ] 4.2.1 Implement GET /api/lineage/nodes to return all graph nodes
- [ ] 4.2.2 Implement GET /api/lineage/edges to return all relationships
- [ ] 4.2.3 Implement GET /api/lineage/search for node/edge search
- [ ] 4.2.4 Implement GET /api/lineage/node/{node_id} for node lineage
- [ ] 4.2.5 Add pagination support for nodes and edges
- [ ] 4.2.6 Format responses for frontend visualization library

### 4.3 Data and File Endpoints
- [ ] 4.3.1 Implement GET /api/files for file listing
- [ ] 4.3.2 Implement GET /api/files/recent for recent files
- [ ] 4.3.3 Implement GET /api/files/search for file search
- [ ] 4.3.4 Implement GET /api/files/stats for file statistics
- [ ] 4.3.5 Implement GET /api/stats for dashboard statistics
- [ ] 4.3.6 Implement GET /api/database/schemas for schema listing
- [ ] 4.3.7 Add file tracking and metadata storage

### 4.4 Activity and Monitoring
- [ ] 4.4.1 Implement GET /api/activity/recent for activity log
- [ ] 4.4.2 Implement GET /api/v1/rag/status for RAG metrics
- [ ] 4.4.3 Add activity tracking system (Redis or database)
- [ ] 4.4.4 Track ingestion events, queries, and errors
- [ ] 4.4.5 Add metrics collection for latencies and cache hits

### 4.5 Admin and Health Endpoints
- [ ] 4.5.1 Implement GET /health with service status checks
- [ ] 4.5.2 Implement POST /admin/restart for container restart
- [ ] 4.5.3 Implement graceful shutdown handler for SIGTERM
- [ ] 4.5.4 Add admin authentication/authorization
- [ ] 4.5.5 Add rate limiting for admin endpoints

### 4.6 Integration and Testing
- [ ] 4.6.1 Update src/api/main_local.py with all new endpoints
- [ ] 4.6.2 Add feature flag for old/new RAG implementations
- [ ] 4.6.3 Ensure backward compatibility for existing endpoints
- [ ] 4.6.4 Add comprehensive API tests for all endpoints
- [ ] 4.6.5 Update OpenAPI/Swagger documentation

## 5. Configuration Management

- [ ] 5.1 Update .env.example with all Docker and LlamaIndex variables
- [ ] 5.2 Add validation for required environment variables on startup
- [ ] 5.3 Create .env.docker for Docker-specific defaults
- [ ] 5.4 Update config/settings.py with LlamaIndex configuration
- [ ] 5.5 Add Ollama connectivity check on startup
- [ ] 5.6 Document all environment variables in comments

## 6. Startup Scripts

- [ ] 6.1 Create start-docker.bat as primary Windows startup script
- [ ] 6.2 Create start-docker.sh for Unix/Linux systems
- [ ] 6.3 Add stop-docker.bat/sh scripts
- [ ] 6.4 Add logs-docker.bat/sh to view container logs
- [ ] 6.5 Update start-local.bat with deprecation warning
- [ ] 6.6 Create check-docker.bat/sh for Docker installation validation
- [ ] 6.7 Add restart-docker.bat/sh scripts

## 7. Testing and Validation

- [ ] 7.1 Test Docker Compose startup with health checks
- [ ] 7.2 Test service dependency ordering (Qdrant → API)
- [ ] 7.3 Test Ollama connectivity from API container
- [ ] 7.4 Test LlamaIndex document indexing with sample SQL
- [ ] 7.5 Test RAG query with context retrieval
- [ ] 7.6 Test hot-reload in development mode
- [ ] 7.7 Test data persistence across container restarts
- [ ] 7.8 Test resource limits (ensure no OOM)
- [ ] 7.9 Test Neo4j cloud and local connections
- [ ] 7.10 Perform load testing (100 concurrent queries)

## 8. Documentation

- [ ] 8.1 Update README.md with Docker-first setup instructions
- [ ] 8.2 Create docs/DOCKER_SETUP.md with comprehensive Docker guide
- [ ] 8.3 Create docs/LLAMAINDEX_RAG.md explaining RAG pipeline
- [ ] 8.4 Update docs/TROUBLESHOOTING.md with Docker issues
- [ ] 8.5 Add architecture diagram showing containerized services + RAG
- [ ] 8.6 Document environment variables in .env.example
- [ ] 8.7 Create migration guide from manual to Docker setup
- [ ] 8.8 Add examples of RAG queries in documentation

## 9. Redis Integration

- [ ] 9.1 Implement embedding cache using Redis
- [ ] 9.2 Add cache hit/miss metrics
- [ ] 9.3 Implement query result caching
- [ ] 9.4 Add cache invalidation strategy
- [ ] 9.5 Add Redis connection health check

## 10. Monitoring and Logging

- [ ] 10.1 Add structured logging for LlamaIndex operations
- [ ] 10.2 Log query latencies and token counts
- [ ] 10.3 Add Prometheus metrics endpoint (future)
- [ ] 10.4 Log Docker container health status
- [ ] 10.5 Add alerting for failed health checks (future)

## 11. Optional Enhancements

- [ ] 11.1 Add Jupyter notebook with LlamaIndex examples
- [ ] 11.2 Create example SQL files for testing RAG
- [ ] 11.3 Add LlamaIndex observability (tracing)
- [ ] 11.4 Implement multi-query retrieval
- [ ] 11.5 Add re-ranking for better relevance

## 12. Cleanup and Finalization

- [ ] 12.1 Remove unused code after feature flag removal
- [ ] 12.2 Update .gitignore for Docker artifacts
- [ ] 12.3 Add .dockerignore for efficient builds
- [ ] 12.4 Verify all tests pass in Docker environment
- [ ] 12.5 Final code review and optimization
- [ ] 12.6 Create release notes documenting changes
