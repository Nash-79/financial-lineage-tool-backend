"""
Application constants for Financial Lineage Tool.

This module contains all magic numbers, default values, and configuration
constants used throughout the application.
"""

from __future__ import annotations

# Embedding configuration
EMBEDDING_DIMENSION = 768  # nomic-embed-text embedding size
DEFAULT_SIMILARITY_TOP_K = 5  # Default number of results for vector search

# Chunking configuration
DEFAULT_CHUNK_SIZE = 512  # tokens
DEFAULT_CHUNK_OVERLAP = 50  # tokens
MAX_CHUNK_SIZE = 1500  # Maximum tokens per chunk

# Cache configuration
QUERY_CACHE_TTL = 3600  # 1 hour in seconds
EMBEDDING_CACHE_TTL = 86400  # 24 hours in seconds

# API configuration
DEFAULT_REQUEST_TIMEOUT = 120  # seconds
MAX_BATCH_SIZE = 50  # Maximum items per batch operation

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s"

# File size limits
MAX_FILE_SIZE_MB = 100  # Maximum file size for ingestion

# Model configuration
DEFAULT_LLM_MODEL = "llama3.1:8b"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_LLM_TEMPERATURE = 0.1

# Database configuration
QDRANT_COLLECTION_NAME = "code_chunks"
NEO4J_DEFAULT_DATABASE = "neo4j"

# Activity tracking
MAX_ACTIVITY_EVENTS = 10000  # Maximum events to keep in memory
