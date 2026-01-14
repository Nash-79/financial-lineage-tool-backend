"""API configuration for local development."""

from __future__ import annotations

import os
import logging
import sys

# Configure logger for configuration validation
logger = logging.getLogger(__name__)


class LocalConfig:
    """Local development configuration.

    Manages environment-based configuration for all services:
    - Ollama (local LLM and embeddings)
    - LlamaIndex (RAG framework)
    - Qdrant (vector database)
    - Neo4j (graph database)
    - Redis (caching)
    - Storage paths
    - Security (JWT, CORS, credentials)
    """

    # Environment mode
    ENVIRONMENT = os.getenv(
        "ENVIRONMENT", "development"
    )  # development, staging, production

    # Security settings
    # Development default secret - MUST be overridden in production
    _DEV_JWT_SECRET = "dev-only-secret-key-do-not-use-in-production-32chars"
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        (
            _DEV_JWT_SECRET
            if os.getenv("ENVIRONMENT", "development") != "production"
            else ""
        ),
    )
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    JWT_REQUIRED = (
        os.getenv("JWT_REQUIRED", "false").lower() == "true"
    )  # Enforce auth in non-prod
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")  # Bootstrap admin API key

    # CORS settings
    ALLOWED_ORIGINS = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
    ).split(",")

    # Inference fallback settings
    INFERENCE_FALLBACK_PROVIDER = os.getenv(
        "INFERENCE_FALLBACK_PROVIDER", "openrouter"
    )  # openrouter, none
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_REFERER = os.getenv(
        "OPENROUTER_REFERER", "https://github.com/your-repo"
    )
    # Free-tier models verified as $0/M input and $0/M output on OpenRouter
    # See: https://openrouter.ai/models?q=:free
    _DEFAULT_FREE_TIER_MODELS = [
        "google/gemini-2.0-flash-exp:free",  # Fast, general-purpose, large context
        "mistralai/mistral-7b-instruct:free",  # Balanced chat model
        "mistralai/devstral-2512:free",  # 262K context, code/architecture specialist
        "meta-llama/llama-3.1-8b-instruct:free",  # General chat
        "deepseek/deepseek-r1-0528:free",  # 164K context, deep reasoning/CoT
        "qwen/qwen3-4b:free",  # Fast, efficient for semantic/text tasks
    ]
    FREE_TIER_MODELS = [
        model.strip()
        for model in os.getenv(
            "FREE_TIER_MODELS", ",".join(_DEFAULT_FREE_TIER_MODELS)
        ).split(",")
        if model.strip()
    ]
    DEFAULT_FREE_TIER_MODEL = os.getenv(
        "DEFAULT_FREE_TIER_MODEL",
        _DEFAULT_FREE_TIER_MODELS[0] if _DEFAULT_FREE_TIER_MODELS else "",
    )
    if DEFAULT_FREE_TIER_MODEL and DEFAULT_FREE_TIER_MODEL not in FREE_TIER_MODELS:
        FREE_TIER_MODELS.append(DEFAULT_FREE_TIER_MODEL)
    INFERENCE_DEFAULT_MODEL = os.getenv(
        "INFERENCE_DEFAULT_MODEL", DEFAULT_FREE_TIER_MODEL
    )

    # Ollama settings
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    # Limit context window to prevent OOM on 16GB RAM machines (Default: 4096)
    OLLAMA_CONTEXT_WINDOW = int(os.getenv("OLLAMA_CONTEXT_WINDOW", "4096"))
    # Use quantized models to reduce memory usage (50% reduction)
    OLLAMA_USE_QUANTIZED = os.getenv("OLLAMA_USE_QUANTIZED", "false").lower() == "true"

    # LlamaIndex settings
    USE_LLAMAINDEX = os.getenv("USE_LLAMAINDEX", "false").lower() == "true"
    SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", "5"))

    # Chat model routing (OpenRouter free-tier)
    # Optimized routing based on model capabilities:
    # - /deep: reasoning-first (DeepSeek R1 for CoT) with code fallback (Devstral)
    # - /graph: code/structure-first (Devstral) with reasoning fallback (DeepSeek R1)
    # - /semantic and /text: speed-first (Gemini, Qwen, Mistral 7B)
    CHAT_DEEP_PRIMARY_MODEL = os.getenv(
        "CHAT_DEEP_PRIMARY_MODEL", "deepseek/deepseek-r1-0528:free"
    )
    CHAT_DEEP_SECONDARY_MODEL = os.getenv(
        "CHAT_DEEP_SECONDARY_MODEL", "mistralai/devstral-2512:free"
    )
    CHAT_DEEP_TERTIARY_MODEL = os.getenv(
        "CHAT_DEEP_TERTIARY_MODEL", "google/gemini-2.0-flash-exp:free"
    )
    CHAT_GRAPH_PRIMARY_MODEL = os.getenv(
        "CHAT_GRAPH_PRIMARY_MODEL", "mistralai/devstral-2512:free"
    )
    CHAT_GRAPH_SECONDARY_MODEL = os.getenv(
        "CHAT_GRAPH_SECONDARY_MODEL", "deepseek/deepseek-r1-0528:free"
    )
    CHAT_GRAPH_TERTIARY_MODEL = os.getenv(
        "CHAT_GRAPH_TERTIARY_MODEL", "google/gemini-2.0-flash-exp:free"
    )
    CHAT_SEMANTIC_PRIMARY_MODEL = os.getenv(
        "CHAT_SEMANTIC_PRIMARY_MODEL", "google/gemini-2.0-flash-exp:free"
    )
    CHAT_SEMANTIC_SECONDARY_MODEL = os.getenv(
        "CHAT_SEMANTIC_SECONDARY_MODEL", "qwen/qwen3-4b:free"
    )
    CHAT_SEMANTIC_TERTIARY_MODEL = os.getenv(
        "CHAT_SEMANTIC_TERTIARY_MODEL", "mistralai/mistral-7b-instruct:free"
    )
    CHAT_TEXT_PRIMARY_MODEL = os.getenv(
        "CHAT_TEXT_PRIMARY_MODEL", "google/gemini-2.0-flash-exp:free"
    )
    CHAT_TEXT_SECONDARY_MODEL = os.getenv(
        "CHAT_TEXT_SECONDARY_MODEL", "mistralai/mistral-7b-instruct:free"
    )
    CHAT_TEXT_TERTIARY_MODEL = os.getenv(
        "CHAT_TEXT_TERTIARY_MODEL", "qwen/qwen3-4b:free"
    )
    CHAT_TITLE_PRIMARY_MODEL = os.getenv(
        "CHAT_TITLE_PRIMARY_MODEL", "google/gemini-2.0-flash-exp:free"
    )
    CHAT_TITLE_SECONDARY_MODEL = os.getenv(
        "CHAT_TITLE_SECONDARY_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
    )
    CHAT_TITLE_TERTIARY_MODEL = os.getenv(
        "CHAT_TITLE_TERTIARY_MODEL", "mistralai/mistral-7b-instruct:free"
    )

    # Chat temperatures
    CHAT_DEEP_TEMPERATURE = float(os.getenv("CHAT_DEEP_TEMPERATURE", "0.6"))
    CHAT_GRAPH_TEMPERATURE = float(os.getenv("CHAT_GRAPH_TEMPERATURE", "0.1"))
    CHAT_SEMANTIC_TEMPERATURE = float(os.getenv("CHAT_SEMANTIC_TEMPERATURE", "0.2"))
    CHAT_TEXT_TEMPERATURE = float(os.getenv("CHAT_TEXT_TEMPERATURE", "0.3"))
    CHAT_TITLE_TEMPERATURE = float(os.getenv("CHAT_TITLE_TEMPERATURE", "0.2"))

    # Chat timeouts (seconds)
    CHAT_TIMEOUT_DEEP_SECONDS = float(os.getenv("CHAT_TIMEOUT_DEEP_SECONDS", "120"))
    CHAT_TIMEOUT_GRAPH_SECONDS = float(os.getenv("CHAT_TIMEOUT_GRAPH_SECONDS", "60"))
    CHAT_TIMEOUT_SEMANTIC_SECONDS = float(
        os.getenv("CHAT_TIMEOUT_SEMANTIC_SECONDS", "60")
    )
    CHAT_TIMEOUT_TEXT_SECONDS = float(os.getenv("CHAT_TIMEOUT_TEXT_SECONDS", "45"))
    CHAT_TIMEOUT_TITLE_SECONDS = float(os.getenv("CHAT_TIMEOUT_TITLE_SECONDS", "45"))

    # Chat fallback behavior
    CHAT_RETRY_BASE_DELAY_SECONDS = float(
        os.getenv("CHAT_RETRY_BASE_DELAY_SECONDS", "2.0")
    )
    CHAT_RETRY_BACKOFF_FACTOR = float(
        os.getenv("CHAT_RETRY_BACKOFF_FACTOR", "2.0")
    )
    CHAT_MAX_RETRIES = int(os.getenv("CHAT_MAX_RETRIES", "3"))
    CHAT_CONTEXT_TOKEN_LIMIT = int(os.getenv("CHAT_CONTEXT_TOKEN_LIMIT", "8000"))

    # Chat retrieval settings
    CHAT_DEEP_TOP_K = int(os.getenv("CHAT_DEEP_TOP_K", "10"))
    CHAT_SEMANTIC_TOP_K = int(os.getenv("CHAT_SEMANTIC_TOP_K", "5"))
    CHAT_GRAPH_TOP_K = int(os.getenv("CHAT_GRAPH_TOP_K", "3"))
    CHAT_DEEP_GRAPH_HOPS = int(os.getenv("CHAT_DEEP_GRAPH_HOPS", "2"))
    CHAT_GRAPH_MAX_HOPS = int(os.getenv("CHAT_GRAPH_MAX_HOPS", "3"))
    CHAT_STREAM_CHUNK_SIZE = int(os.getenv("CHAT_STREAM_CHUNK_SIZE", "200"))
    _DEFAULT_CHAT_JSON_MODELS = [
        "deepseek/deepseek-r1-0528:free",
    ]
    CHAT_JSON_MODELS = [
        model.strip()
        for model in os.getenv(
            "CHAT_JSON_MODELS", ",".join(_DEFAULT_CHAT_JSON_MODELS)
        ).split(",")
        if model.strip()
    ]

    # Qdrant settings
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "code_chunks")
    QDRANT_HNSW_EF_CONSTRUCT = int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT", "100"))
    QDRANT_HNSW_M = int(os.getenv("QDRANT_HNSW_M", "16"))
    ENABLE_HYBRID_SEARCH = os.getenv("ENABLE_HYBRID_SEARCH", "true").lower() == "true"

    # Neo4j settings
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://66e1cb8c.databases.neo4j.io")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")  # REQUIRED in production
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

    # Redis settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    USE_CACHE_WARMING = os.getenv("USE_CACHE_WARMING", "false").lower() == "true"

    # Storage
    STORAGE_PATH = os.getenv("STORAGE_PATH", "./data")
    LOG_PATH = os.getenv("LOG_PATH", "./logs")

    # DuckDB metadata storage
    # Mode: "memory" for in-memory with snapshots, "persistent" for file-based
    DUCKDB_MODE = os.getenv("DUCKDB_MODE", "memory")  # Default to in-memory mode
    DUCKDB_PATH = os.getenv(
        "DUCKDB_PATH", ":memory:" if DUCKDB_MODE == "memory" else "data/metadata.duckdb"
    )

    # Snapshot settings (for in-memory mode)
    DUCKDB_SNAPSHOT_INTERVAL_MINUTES = int(
        os.getenv("DUCKDB_SNAPSHOT_INTERVAL_MINUTES", "5")
    )
    DUCKDB_SNAPSHOT_RETENTION_COUNT = int(
        os.getenv("DUCKDB_SNAPSHOT_RETENTION_COUNT", "5")
    )

    # Chat artifact retention (days before cleanup)
    CHAT_ARTIFACT_RETENTION_DAYS = int(
        os.getenv("CHAT_ARTIFACT_RETENTION_DAYS", "90")
    )

    # File upload settings
    UPLOAD_BASE_DIR = os.getenv("UPLOAD_BASE_DIR", "data/raw/uploaded")
    UPLOAD_MAX_FILE_SIZE_MB = int(os.getenv("UPLOAD_MAX_FILE_SIZE_MB", "50"))

    # Allowed file extensions for ingestion (comma-separated)
    # Can be overridden via environment variable
    ALLOWED_FILE_EXTENSIONS = os.getenv(
        "ALLOWED_FILE_EXTENSIONS", ".sql,.ddl,.csv,.json,.py,.ipynb"
    ).split(",")

    # WebSocket configuration
    WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://127.0.0.1:8000/admin/ws/dashboard")

    # GitHub OAuth settings
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI = os.getenv(
        "GITHUB_REDIRECT_URI", "http://localhost:8080/connectors/github/callback"
    )

    # OpenTelemetry (SigNoz) settings
    OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "financial-lineage-backend")
    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    @classmethod
    def validate_production_config(cls) -> None:
        """Validate that required configuration is set for production deployment.

        Raises:
            ValueError: If required production configuration is missing.
        """
        if cls.ENVIRONMENT != "production":
            logger.info(
                f"Running in {cls.ENVIRONMENT} mode - skipping strict validation"
            )
            return

        errors = []

        # Required credentials
        if not cls.NEO4J_PASSWORD:
            errors.append(
                "NEO4J_PASSWORD must be set via environment variable in production"
            )

        if not cls.JWT_SECRET_KEY:
            errors.append(
                "JWT_SECRET_KEY must be set via environment variable in production"
            )
        elif len(cls.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters for security")

        # CORS validation
        if not cls.ALLOWED_ORIGINS or cls.ALLOWED_ORIGINS == ["*"]:
            errors.append(
                "ALLOWED_ORIGINS must be explicitly configured (wildcards not allowed in production)"
            )

        if errors:
            error_msg = "Production configuration validation failed:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            logger.error(error_msg)
            sys.exit(1)

        logger.info("Production configuration validated successfully")

    @staticmethod
    def mask_sensitive(value: str, visible_chars: int = 4) -> str:
        """Mask sensitive configuration values for logging.

        Args:
            value: The sensitive value to mask
            visible_chars: Number of characters to show at the end

        Returns:
            Masked string like "***xyz" or "***" if value is too short
        """
        if not value or len(value) <= visible_chars:
            return "***"
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]

    @classmethod
    def get_llm_model(cls) -> str:
        """Get the LLM model name, returning quantized variant if enabled.

        Returns:
            Model name (e.g., "llama3.1:8b" or "llama3.1:8b-q4_0")
        """
        if cls.OLLAMA_USE_QUANTIZED and not cls.LLM_MODEL.endswith(
            ("-q4_0", "-q4_K_M", "-q8_0")
        ):
            # Add q4_0 quantization suffix for 50% memory reduction
            base_model = cls.LLM_MODEL.split(":")[0]
            version = cls.LLM_MODEL.split(":")[1] if ":" in cls.LLM_MODEL else "latest"
            return f"{base_model}:{version}-q4_0"
        return cls.LLM_MODEL

    @classmethod
    def get_chat_endpoint_models(cls) -> dict:
        """Return chat endpoint model mappings for config endpoints."""
        return {
            "/api/chat/deep": {
                "primary": cls.CHAT_DEEP_PRIMARY_MODEL,
                "secondary": cls.CHAT_DEEP_SECONDARY_MODEL,
                "tertiary": cls.CHAT_DEEP_TERTIARY_MODEL,
            },
            "/api/chat/graph": {
                "primary": cls.CHAT_GRAPH_PRIMARY_MODEL,
                "secondary": cls.CHAT_GRAPH_SECONDARY_MODEL,
                "tertiary": cls.CHAT_GRAPH_TERTIARY_MODEL,
            },
            "/api/chat/semantic": {
                "primary": cls.CHAT_SEMANTIC_PRIMARY_MODEL,
                "secondary": cls.CHAT_SEMANTIC_SECONDARY_MODEL,
                "tertiary": cls.CHAT_SEMANTIC_TERTIARY_MODEL,
            },
            "/api/chat/text": {
                "primary": cls.CHAT_TEXT_PRIMARY_MODEL,
                "secondary": cls.CHAT_TEXT_SECONDARY_MODEL,
                "tertiary": cls.CHAT_TEXT_TERTIARY_MODEL,
            },
            "/api/chat/title": {
                "primary": cls.CHAT_TITLE_PRIMARY_MODEL,
                "secondary": cls.CHAT_TITLE_SECONDARY_MODEL,
                "tertiary": cls.CHAT_TITLE_TERTIARY_MODEL,
            },
        }

    @classmethod
    def get_chat_endpoint_temperatures(cls) -> dict:
        """Return chat endpoint temperatures."""
        return {
            "deep": cls.CHAT_DEEP_TEMPERATURE,
            "graph": cls.CHAT_GRAPH_TEMPERATURE,
            "semantic": cls.CHAT_SEMANTIC_TEMPERATURE,
            "text": cls.CHAT_TEXT_TEMPERATURE,
            "title": cls.CHAT_TITLE_TEMPERATURE,
        }

    @classmethod
    def get_chat_endpoint_timeouts(cls) -> dict:
        """Return chat endpoint timeouts in seconds."""
        return {
            "deep": cls.CHAT_TIMEOUT_DEEP_SECONDS,
            "graph": cls.CHAT_TIMEOUT_GRAPH_SECONDS,
            "semantic": cls.CHAT_TIMEOUT_SEMANTIC_SECONDS,
            "text": cls.CHAT_TIMEOUT_TEXT_SECONDS,
            "title": cls.CHAT_TIMEOUT_TITLE_SECONDS,
        }


config = LocalConfig()

# Validate production configuration on module import
if config.ENVIRONMENT == "production":
    config.validate_production_config()
