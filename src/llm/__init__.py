"""
LLM services for Financial Lineage Tool.

This module avoids importing heavy optional dependencies eagerly. Components
that require LlamaIndex will be None if the dependency is missing, allowing
lighter modules (e.g., InferenceRouter) to be imported for testing without
installing the full stack.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from .llamaindex_service import LlamaIndexService, RAGMetrics  # type: ignore
except Exception as e:  # pragma: no cover - optional dependency guard
    logger.debug(f"LlamaIndexService not imported (missing optional deps): {e}")
    LlamaIndexService = None  # type: ignore
    RAGMetrics = None  # type: ignore

from .inference_router import InferenceRouter, CancelledRequestError

__all__ = [
    "LlamaIndexService",
    "RAGMetrics",
    "InferenceRouter",
    "CancelledRequestError",
]
