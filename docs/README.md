# Financial Lineage Tool - Documentation Index

This directory contains all documentation for the Financial Lineage Tool project.

## Quick Start

**New users start here**:
1. [Docker Setup Guide](setup/DOCKER_SETUP.md) - **Recommended:** Start with Docker
2. [Getting Started](setup/GETTING_STARTED.md) - Quick start guide
3. [Architecture Overview](architecture/ARCHITECTURE.md) - Understand the system

## Documentation by Category

### Core Components

| Document | Description |
|----------|-------------|
| [Ingestion Overview](ingestion/INGESTION_OVERVIEW.md) | Run-scoped ingestion pipeline and artifacts |
| [Vector Ingestion Architecture](ingestion/VECTOR_INGESTION_ARCHITECTURE.md) | Chunking and vector indexing details |
| [Knowledge Graph Architecture](knowledge-graph/KNOWLEDGE_GRAPH_ARCHITECTURE.md) | Neo4j schema and enrichment flow |
| [Lineage Overview](knowledge-graph/LINEAGE_OVERVIEW.md) | Current lineage behavior and edge metadata |
| [Chat Overview](chat/CHAT_OVERVIEW.md) | Chat endpoints and routing logic |

### Setup & Installation

| Document | Description |
|----------|-------------|
| [Docker Setup](setup/DOCKER_SETUP.md) | **Recommended:** Docker-based deployment |
| [Getting Started](setup/GETTING_STARTED.md) | Quick start guide |
| [Docker Services](setup/DOCKER_SERVICES.md) | Docker service documentation |
| [Docker Troubleshooting](setup/DOCKER_TROUBLESHOOTING.md) | Docker troubleshooting |
| [Local Setup Guide](setup/LOCAL_SETUP_GUIDE.md) | **Deprecated:** Manual local setup |

### User Guides

| Document | Description |
|----------|-------------|
| [SQL Organizer Quickstart](ingestion/legacy/SQL_ORGANIZER_QUICKSTART.md) | Legacy SQL organizer quick start |
| [Hierarchical Organization Guide](ingestion/legacy/HIERARCHICAL_ORGANIZATION_GUIDE.md) | Legacy SQL organizer deep dive |
| [File Watcher Guide](ingestion/legacy/FILE_WATCHER_GUIDE.md) | Legacy file watcher workflow |
| [Export Guide](guides/EXPORT_GUIDE.md) | Exporting data from knowledge graph and embeddings |
| [AdventureWorks Guide](guides/ADVENTUREWORKS_GUIDE.md) | Working with AdventureWorks sample database |

### Architecture & API

| Document | Description |
|----------|-------------|
| [Architecture](architecture/ARCHITECTURE.md) | System architecture and component overview |
| [LlamaIndex RAG](architecture/LLAMAINDEX_RAG.md) | RAG pipeline documentation |
| [Implementation Status](architecture/IMPLEMENTATION_STATUS.md) | Current implementation status and roadmap |
| [API Reference](api/API_REFERENCE.md) | Complete API endpoint documentation |

### Database Configuration

| Document | Description |
|----------|-------------|
| [Qdrant Setup](database/QDRANT_SETUP.md) | Qdrant vector database setup |
| [Gremlin Setup](database/GREMLIN_SETUP.md) | Azure Cosmos DB Gremlin API setup |

### Troubleshooting

| Document | Description |
|----------|-------------|
| [Troubleshooting Guide](troubleshooting/TROUBLESHOOTING.md) | Common issues and solutions |
| [Implementation Summary](troubleshooting/IMPLEMENTATION_SUMMARY.md) | Implementation notes and lessons learned |
| [Next Steps](troubleshooting/NEXT_STEPS.md) | Planned improvements and roadmap |

## Documentation by Workflow

### I want to get started quickly

1. [Docker Setup](setup/DOCKER_SETUP.md) - **Start here!** Docker-based deployment
2. [Getting Started](setup/GETTING_STARTED.md) - Quick start guide
3. [Architecture Overview](architecture/ARCHITECTURE.md) - Understand the system
4. [API Reference](api/API_REFERENCE.md) - Explore the API

### I want to ingest files (current pipeline)

1. [Ingestion Overview](ingestion/INGESTION_OVERVIEW.md) - Run-scoped ingestion flow
2. [API Reference](api/API_REFERENCE.md) - Ingest endpoints and request shapes
3. [Vector Ingestion Architecture](ingestion/VECTOR_INGESTION_ARCHITECTURE.md) - Chunking + embeddings
4. [Knowledge Graph Architecture](knowledge-graph/KNOWLEDGE_GRAPH_ARCHITECTURE.md) - Graph ingestion + snapshots

### I want to organize SQL files

1. [SQL Organizer Quickstart](ingestion/legacy/SQL_ORGANIZER_QUICKSTART.md) - Legacy organizer usage
2. [Hierarchical Organization Guide](ingestion/legacy/HIERARCHICAL_ORGANIZATION_GUIDE.md) - Legacy advanced organization
3. [File Watcher Guide](ingestion/legacy/FILE_WATCHER_GUIDE.md) - Legacy automatic processing

### I want to set up the environment

1. [Docker Setup](setup/DOCKER_SETUP.md) - **Recommended:** Docker deployment
2. [Docker Troubleshooting](setup/DOCKER_TROUBLESHOOTING.md) - Docker issues
3. [Qdrant Setup](database/QDRANT_SETUP.md) - Vector database setup
4. [Gremlin Setup](database/GREMLIN_SETUP.md) - Cosmos DB setup (legacy)

### I want to understand the system

1. [Architecture](architecture/ARCHITECTURE.md) - System overview
2. [LlamaIndex RAG](architecture/LLAMAINDEX_RAG.md) - RAG pipeline details
3. [Knowledge Graph Architecture](knowledge-graph/KNOWLEDGE_GRAPH_ARCHITECTURE.md) - Neo4j schema and edges
4. [Vector Ingestion Architecture](ingestion/VECTOR_INGESTION_ARCHITECTURE.md) - Chunking + embeddings
5. [Chat Overview](chat/CHAT_OVERVIEW.md) - Chat routing and endpoints
6. [Implementation Status](architecture/IMPLEMENTATION_STATUS.md) - Current status
7. [AdventureWorks Guide](guides/ADVENTUREWORKS_GUIDE.md) - Sample data

### I want to export data

1. [Export Guide](guides/EXPORT_GUIDE.md) - Export embeddings and graph data

### I need help troubleshooting

1. [Docker Troubleshooting](setup/DOCKER_TROUBLESHOOTING.md) - Docker-specific issues
2. [Troubleshooting Guide](troubleshooting/TROUBLESHOOTING.md) - General troubleshooting
3. [Implementation Summary](troubleshooting/IMPLEMENTATION_SUMMARY.md) - Implementation notes

## Quick Reference

### SQL Organization Commands

Note: These commands use the legacy organizer pipeline (`data/raw` -> `data/separated_sql`).

```bash
# Hierarchical organization (recommended)
python examples/test_hierarchical_organizer.py

# Start file watcher (automatic processing)
python examples/start_file_watcher.py

# Basic organization (flat structure)
python examples/demo_sql_organizer.py
```

### Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run API locally
python src/api/main_local.py

# Run tests
pytest tests/
```

### Utility Scripts

All utility scripts are in the `scripts/` folder:

```bash
# Add AdventureWorks entities to graph
python scripts/add_adventureworks_entities.py

# Export graph data
python scripts/export_graph_json.py

# Export embeddings
python scripts/export_embeddings_json.py

# Query Neo4j
python scripts/query_neo4j.py

# Test Qdrant
python scripts/test_qdrant.py
```

## File Organization

```
docs/
  README.md
  api/
    API_REFERENCE.md
    AUTHENTICATION.md
  architecture/
    ARCHITECTURE.md
    LLAMAINDEX_RAG.md
    IMPLEMENTATION_STATUS.md
  chat/
    CHAT_OVERVIEW.md
  ingestion/
    INGESTION_OVERVIEW.md
    VECTOR_INGESTION_ARCHITECTURE.md
    PARALLEL_PROCESSING_GUIDE.md
    legacy/
      SQL_ORGANIZER_QUICKSTART.md
      HIERARCHICAL_ORGANIZATION_GUIDE.md
      FILE_WATCHER_GUIDE.md
  knowledge-graph/
    KNOWLEDGE_GRAPH_ARCHITECTURE.md
    LINEAGE_OVERVIEW.md
  guides/
    EXPORT_GUIDE.md
    ADVENTUREWORKS_GUIDE.md
    PLUGIN_DEVELOPMENT_GUIDE.md
    USER_CONTEXT_GUIDE.md
  setup/
    DOCKER_SETUP.md
    GETTING_STARTED.md
    DOCKER_SERVICES.md
    DOCKER_TROUBLESHOOTING.md
    LOCAL_SETUP_GUIDE.md
  operations/
    DEPLOYMENT_GUIDE.md
    MONITORING_GUIDE.md
    QDRANT_TUNING.md
    ROLLBACK_PROCEDURES.md
  database/
    QDRANT_SETUP.md
    GREMLIN_SETUP.md
  troubleshooting/
    TROUBLESHOOTING.md
    IMPLEMENTATION_SUMMARY.md
    NEXT_STEPS.md
```

## Contributing

When adding new documentation:

1. **Choose correct category** - Place in appropriate subdirectory (setup/, guides/, etc.)
2. **Update this hub** - Add your document to the tables above
3. **Use descriptive names** - Follow UPPER_SNAKE_CASE.md convention
4. **Link related docs** - Cross-reference related documentation
5. **Keep root clean** - Only essential docs in project root

## Document Templates

### Guide Template

```markdown
# [Feature Name] - Guide

## Overview
Brief description of the feature

## Quick Start
Step-by-step getting started

## Usage
Detailed usage instructions

## Configuration
Configuration options

## Examples
Practical examples

## Troubleshooting
Common issues and solutions

## Advanced Topics
Advanced usage patterns
```

### Reference Template

```markdown
# [Component Name] - Reference

## Overview
Component description

## API Reference
API documentation

## Configuration
Configuration options

## Examples
Code examples

## Related Documentation
Links to related docs
```

## Getting Help

- **Documentation Issues**: Check the specific guide in the appropriate category
- **Setup Issues**: See [Docker Setup](setup/DOCKER_SETUP.md) or [Docker Troubleshooting](setup/DOCKER_TROUBLESHOOTING.md)
- **Architecture Questions**: See [Architecture](architecture/ARCHITECTURE.md)
- **API Questions**: See [API Reference](api/API_REFERENCE.md)

## Documentation Standards

1. **Clarity**: Write for beginners, explain technical terms
2. **Completeness**: Include all necessary information
3. **Examples**: Provide practical, working examples
4. **Updates**: Keep documentation current with code changes
5. **Cross-references**: Link to related documentation

---

**Last Updated**: 2026-01-13
**Documentation Version**: 2.1.0 - Reorganized core component docs





