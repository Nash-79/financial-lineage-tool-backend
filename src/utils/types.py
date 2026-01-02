"""
Type aliases and custom types for Financial Lineage Tool.

This module defines common type aliases used throughout the application
to improve code readability and type safety.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

# Common type aliases
JSON = Dict[str, Any]
JSONList = List[Dict[str, Any]]
Vector = List[float]
Metadata = Dict[str, Any]

# API types
QueryResult = Dict[str, Any]
HealthStatus = Dict[str, Union[str, Dict[str, str]]]

# Ingestion types
ChunkMetadata = Dict[str, Any]
ParsedEntity = Dict[str, Any]

# LLM types
EmbeddingVector = List[float]
LLMResponse = str

# Optional types
OptionalStr = Optional[str]
OptionalInt = Optional[int]
OptionalDict = Optional[Dict[str, Any]]
