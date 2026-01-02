"""
Utility modules for Financial Lineage Tool.

This package provides common utilities, exceptions, constants, type aliases,
validators, and logging configuration used throughout the application.
"""

from __future__ import annotations

from .activity_tracker import ActivityEvent, ActivityTracker, SessionMetrics
from .constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SIMILARITY_TOP_K,
    EMBEDDING_CACHE_TTL,
    EMBEDDING_DIMENSION,
    MAX_ACTIVITY_EVENTS,
    MAX_BATCH_SIZE,
    MAX_CHUNK_SIZE,
    QDRANT_COLLECTION_NAME,
    QUERY_CACHE_TTL,
)
from .exceptions import (
    CacheError,
    ChunkingError,
    ConfigurationError,
    GraphDatabaseError,
    IngestionError,
    LineageToolError,
    LLMError,
    ParsingError,
    ValidationError,
    VectorStoreError,
)
from .logging_config import RequestIDFilter, get_logger, setup_logging
from .types import (
    ChunkMetadata,
    EmbeddingVector,
    HealthStatus,
    JSON,
    JSONList,
    LLMResponse,
    Metadata,
    OptionalDict,
    OptionalInt,
    OptionalStr,
    ParsedEntity,
    QueryResult,
    Vector,
)
from .validators import (
    validate_config,
    validate_env_var,
    validate_file_path,
    validate_port,
)

__all__ = [
    # Activity tracking
    "ActivityEvent",
    "ActivityTracker",
    "SessionMetrics",
    # Constants
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_LLM_MODEL",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_REQUEST_TIMEOUT",
    "DEFAULT_SIMILARITY_TOP_K",
    "EMBEDDING_CACHE_TTL",
    "EMBEDDING_DIMENSION",
    "MAX_ACTIVITY_EVENTS",
    "MAX_BATCH_SIZE",
    "MAX_CHUNK_SIZE",
    "QDRANT_COLLECTION_NAME",
    "QUERY_CACHE_TTL",
    # Exceptions
    "CacheError",
    "ChunkingError",
    "ConfigurationError",
    "GraphDatabaseError",
    "IngestionError",
    "LineageToolError",
    "LLMError",
    "ParsingError",
    "ValidationError",
    "VectorStoreError",
    # Logging
    "RequestIDFilter",
    "get_logger",
    "setup_logging",
    # Types
    "ChunkMetadata",
    "EmbeddingVector",
    "HealthStatus",
    "JSON",
    "JSONList",
    "LLMResponse",
    "Metadata",
    "OptionalDict",
    "OptionalInt",
    "OptionalStr",
    "ParsedEntity",
    "QueryResult",
    "Vector",
    # Validators
    "validate_config",
    "validate_env_var",
    "validate_file_path",
    "validate_port",
]
