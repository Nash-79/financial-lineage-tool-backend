# Docker Services Reference

This document categorizes and explains the Docker services used in the Financial Lineage Tool.

## Service Categories

We categorize services into three roles:
1.  **App Services**: The core application logic.
2.  **InfrastructureDBs**: Persistent storage and state management.
3.  **Tools**: Development and operational utilities.

## Services Overview

### App Services

| Service | Description | Compose File |
|---------|-------------|--------------|
| `api` | The main FastAPI backend. Orchestrates agents, search, and graph operations. | `docker-compose.yml`, `docker-compose.local.yml` |

### InfrastructureDBs

| Service | Description | Compose File |
|---------|-------------|--------------|
| `cosmos-gremlin` | Azure Cosmos DB Emulator (Gremlin API) for Graph storage. | *Used in full Azure setup or emulator* |
| `qdrant` | Vector database for semantic search (Local alternative to Azure AI Search). | `docker-compose.local.yml` |
| `redis` | Caching layer for performance. | `docker-compose.yml`, `docker-compose.local.yml` |

### Tools

| Service | Description | Compose File |
|---------|-------------|--------------|
| `signoz` | Observability UI + OTLP collector for logs, traces, and metrics. | `docker-compose.signoz.yml` |
| `jupyter` | Interactive notebook environment for data exploration. | `docker-compose.local.yml` |

## Environments

### Local Development (`docker-compose.local.yml`)
Designed for zero-cost local development using open-source alternatives.
- **LLM**: Uses Ollama (running on host) instead of Azure OpenAI.
- **Vector DB**: Uses Qdrant instead of Azure AI Search.
- **Graph**: Can connect to local Cosmos Emulator or Neo4j (experimental).

### Azure Integrated (`docker-compose.yml`)
Designed for full feature parity and production-like environments.
- **LLM**: Azure OpenAI.
- **Vector DB**: Azure AI Search.
- **Graph**: Azure Cosmos DB.
