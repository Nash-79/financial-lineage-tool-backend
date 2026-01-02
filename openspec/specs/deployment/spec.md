# deployment Specification

## Purpose
TBD - created by archiving change dockerize-backend-with-huggingface. Update Purpose after archive.
## Requirements
### Requirement: Docker Compose Orchestration
The system SHALL provide Docker Compose configuration that orchestrates all backend services with proper dependency management and health checks.

#### Scenario: Start all services with single command
- **WHEN** user runs `docker compose up`
- **THEN** all services (API, Qdrant, Neo4j) start in correct order
- **AND** services wait for dependencies to be healthy before starting
- **AND** API becomes available at http://localhost:8000

#### Scenario: Service dependency management
- **WHEN** API service starts
- **THEN** it waits for Qdrant to be healthy
- **AND** it waits for Neo4j to be accessible
- **AND** it fails gracefully if dependencies are unavailable

#### Scenario: Development mode with hot-reload
- **WHEN** user runs `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
- **THEN** source code changes are reflected immediately
- **AND** API auto-reloads on file changes
- **AND** bind mounts allow local file editing

### Requirement: Containerized API Service
The system SHALL provide a Dockerfile that builds a production-ready FastAPI container with all dependencies.

#### Scenario: Multi-stage Docker build
- **WHEN** Dockerfile is built
- **THEN** it uses multi-stage build to minimize image size
- **AND** dependencies are installed in builder stage
- **AND** final image contains only runtime requirements
- **AND** image size is optimized (<1GB)

#### Scenario: Health check endpoint
- **WHEN** API container starts
- **THEN** Docker health check calls /health endpoint
- **AND** container is marked healthy when endpoint returns 200
- **AND** unhealthy containers trigger restart

#### Scenario: Environment configuration
- **WHEN** API container starts
- **THEN** it reads configuration from environment variables
- **AND** it validates required variables exist
- **AND** it fails fast with clear error if config is invalid

### Requirement: Persistent Data Storage
The system SHALL use Docker volumes to persist data across container restarts.

#### Scenario: Qdrant data persistence
- **WHEN** Qdrant container is stopped and restarted
- **THEN** vector embeddings are retained
- **AND** collections remain intact
- **AND** no data loss occurs

#### Scenario: Log persistence
- **WHEN** API generates logs
- **THEN** logs are written to mounted volume
- **AND** logs survive container restarts
- **AND** logs are accessible from host filesystem

### Requirement: Service Health Monitoring
The system SHALL implement health checks for all services to ensure availability.

#### Scenario: API health check
- **WHEN** health check runs
- **THEN** it verifies API is responding
- **AND** it checks HuggingFace connectivity
- **AND** it checks Qdrant connectivity
- **AND** it checks Neo4j connectivity
- **AND** returns degraded status if any service is down

#### Scenario: Qdrant health check
- **WHEN** Qdrant health check runs
- **THEN** it verifies Qdrant HTTP API is responding
- **AND** it returns healthy status within 10 seconds

### Requirement: Network Isolation
The system SHALL use Docker networking for service-to-service communication.

#### Scenario: Internal service discovery
- **WHEN** API needs to connect to Qdrant
- **THEN** it uses service name `qdrant` as hostname
- **AND** connection is routed through Docker network
- **AND** no port mapping required for internal communication

#### Scenario: External API access
- **WHEN** external client connects to API
- **THEN** API is accessible on host port 8000
- **AND** internal services are not exposed to host
- **AND** only necessary ports are mapped

### Requirement: Environment-Specific Configuration
The system SHALL support separate configurations for development, staging, and production environments.

#### Scenario: Development environment
- **WHEN** using docker-compose.dev.yml
- **THEN** debug mode is enabled
- **AND** source code is bind-mounted for hot-reload
- **AND** verbose logging is enabled
- **AND** development-specific env vars are used

#### Scenario: Production environment
- **WHEN** using docker-compose.prod.yml
- **THEN** debug mode is disabled
- **AND** optimized settings are used
- **AND** resource limits are enforced
- **AND** production env vars are loaded

### Requirement: Docker Installation Validation
The system SHALL provide scripts to validate Docker installation and requirements.

#### Scenario: Pre-flight check
- **WHEN** user runs setup script
- **THEN** it checks Docker is installed
- **AND** it checks Docker daemon is running
- **AND** it checks minimum Docker version (20.10+)
- **AND** it provides clear error messages for missing requirements

#### Scenario: Resource availability check
- **WHEN** setup script runs
- **THEN** it verifies sufficient disk space (>5GB)
- **AND** it checks available memory (>4GB recommended)
- **AND** it warns if resources are insufficient

### Requirement: Admin Restart Endpoint
The system SHALL provide an admin endpoint to trigger graceful container restart from the frontend UI.

#### Scenario: Frontend-triggered restart
- **WHEN** frontend sends POST request to /admin/restart
- **THEN** API sends SIGTERM signal to itself
- **AND** Docker restart policy automatically restarts the container
- **AND** API returns {"status": "restarting"} response before shutdown
- **AND** restart completes within 30 seconds

#### Scenario: Graceful shutdown on restart
- **WHEN** SIGTERM signal is received
- **THEN** API completes in-flight requests
- **AND** it closes database connections gracefully
- **AND** it flushes logs and caches
- **AND** it exits with code 0

#### Scenario: Docker restart policy enforcement
- **WHEN** API container exits
- **THEN** Docker restart policy is set to "unless-stopped" or "always"
- **AND** container automatically restarts
- **AND** health checks pass after restart
- **AND** downtime is minimized (<30s)

#### Scenario: Restart endpoint security
- **WHEN** unauthorized user accesses /admin/restart
- **THEN** endpoint requires admin authentication
- **AND** it returns 403 Forbidden if not authenticated
- **AND** restart attempts are logged
- **AND** rate limiting prevents abuse

#### Scenario: Restart during active operations
- **WHEN** restart is triggered during ingestion
- **THEN** in-progress operations are allowed to complete
- **AND** shutdown timeout is set to 30 seconds
- **AND** operations exceeding timeout are forcefully terminated
- **AND** state is recoverable after restart

