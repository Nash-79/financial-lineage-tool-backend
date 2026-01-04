"""API configuration for local development."""

from __future__ import annotations

import os


class LocalConfig:
    """Local development configuration.

    Manages environment-based configuration for all services:
    - Ollama (local LLM and embeddings)
    - LlamaIndex (RAG framework)
    - Qdrant (vector database)
    - Neo4j (graph database)
    - Redis (caching)
    - Storage paths
    """

    # Ollama settings
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    # Limit context window to prevent OOM on 16GB RAM machines (Default: 4096)
    OLLAMA_CONTEXT_WINDOW = int(os.getenv("OLLAMA_CONTEXT_WINDOW", "4096"))

    # LlamaIndex settings
    USE_LLAMAINDEX = os.getenv("USE_LLAMAINDEX", "false").lower() == "true"
    SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", "5"))
    RESPONSE_MODE = os.getenv("RESPONSE_MODE", "compact")

    # Qdrant settings
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "code_chunks")

    # Neo4j settings
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://66e1cb8c.databases.neo4j.io")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv(
        "NEO4J_PASSWORD", "S6OFtX78rqAyI7Zk9tcpnDAzyN1srKiq4so53WSBWhg"
    )
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

    # Redis settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    # Storage
    STORAGE_PATH = os.getenv("STORAGE_PATH", "./data")
    LOG_PATH = os.getenv("LOG_PATH", "./logs")

    # DuckDB metadata storage
    DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/metadata.duckdb")

    # File upload settings
    UPLOAD_BASE_DIR = os.getenv("UPLOAD_BASE_DIR", "data/raw/uploaded")
    UPLOAD_MAX_FILE_SIZE_MB = int(os.getenv("UPLOAD_MAX_FILE_SIZE_MB", "50"))

    # Allowed file extensions for ingestion (comma-separated)
    # Can be overridden via environment variable
    ALLOWED_FILE_EXTENSIONS = os.getenv(
        "ALLOWED_FILE_EXTENSIONS",
        ".sql,.ddl,.csv,.json,.py,.ipynb"
    ).split(",")
    
    # WebSocket configuration
    WEBSOCKET_URL = os.getenv(
        "WEBSOCKET_URL",
        "ws://127.0.0.1:8000/admin/ws/dashboard"
    )

    # GitHub OAuth settings
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI = os.getenv(
        "GITHUB_REDIRECT_URI",
        "http://localhost:8080/connectors/github/callback"
    )


config = LocalConfig()
