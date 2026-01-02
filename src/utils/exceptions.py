"""
Custom exception hierarchy for Financial Lineage Tool.

This module defines all custom exceptions used throughout the application,
providing clear error categorization and better error handling.
"""

from __future__ import annotations


class LineageToolError(Exception):
    """Base exception for all Financial Lineage Tool errors."""

    pass


class ConfigurationError(LineageToolError):
    """Raised when configuration is invalid or missing."""

    pass


class IngestionError(LineageToolError):
    """Raised during document ingestion or processing."""

    pass


class VectorStoreError(LineageToolError):
    """Raised for vector database operations errors."""

    pass


class GraphDatabaseError(LineageToolError):
    """Raised for graph database operations errors."""

    pass


class LLMError(LineageToolError):
    """Raised for LLM or embedding generation errors."""

    pass


class CacheError(LineageToolError):
    """Raised for caching operations errors."""

    pass


class ValidationError(LineageToolError):
    """Raised when data validation fails."""

    pass


class ParsingError(IngestionError):
    """Raised when SQL or code parsing fails."""

    pass


class ChunkingError(IngestionError):
    """Raised when semantic chunking fails."""

    pass
