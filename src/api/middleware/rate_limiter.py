"""
Rate Limiting Middleware for FastAPI.

Uses slowapi with Redis backend for distributed rate limiting.
Provides per-user and per-endpoint rate limiting with configurable quotas.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from ..config import config

logger = logging.getLogger(__name__)


# ==================== Rate Limit Key Functions ====================


def get_user_identifier(request: Request) -> str:
    """Get rate limit key based on authenticated user or IP.

    Priority:
    1. Authenticated user ID (from JWT)
    2. API key identifier
    3. Remote IP address (fallback)

    Args:
        request: FastAPI request object.

    Returns:
        Unique identifier for rate limiting.
    """
    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        if hasattr(user, "user_id") and user.user_id != "anonymous":
            return f"user:{user.user_id}"

    # Check for API key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use first 8 chars as identifier (don't expose full key)
        return f"apikey:{api_key[:8]}"

    # Fallback to IP address
    return f"ip:{get_remote_address(request)}"


# ==================== Rate Limiter Configuration ====================


# Default rate limits (can be overridden via env vars)
DEFAULT_RATE_LIMIT = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
CHAT_RATE_LIMIT = os.getenv("RATE_LIMIT_CHAT", "30/minute")
INGEST_RATE_LIMIT = os.getenv("RATE_LIMIT_INGEST", "10/minute")
AUTH_RATE_LIMIT = os.getenv("RATE_LIMIT_AUTH", "5/minute")

# Redis URL for distributed rate limiting
REDIS_URL = f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/1"


def create_limiter() -> Limiter:
    """Create and configure the rate limiter.

    Uses Redis as storage backend for distributed rate limiting.
    Falls back to in-memory storage if Redis is unavailable.

    Returns:
        Configured Limiter instance.
    """
    try:
        # Try to use Redis for distributed rate limiting
        limiter = Limiter(
            key_func=get_user_identifier,
            default_limits=[DEFAULT_RATE_LIMIT],
            storage_uri=REDIS_URL,
            strategy="fixed-window",
        )
        logger.info(f"Rate limiter initialized with Redis storage: {REDIS_URL}")
        return limiter
    except Exception as e:
        logger.warning(f"Redis unavailable for rate limiting, using in-memory: {e}")
        # Fallback to in-memory (not suitable for multiple workers)
        limiter = Limiter(
            key_func=get_user_identifier,
            default_limits=[DEFAULT_RATE_LIMIT],
            strategy="fixed-window",
        )
        return limiter


# Global limiter instance
limiter = create_limiter()


# ==================== Setup Functions ====================


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting middleware for the FastAPI application.

    Args:
        app: FastAPI application instance.
    """
    # Add limiter to app state
    app.state.limiter = limiter

    # Add middleware
    app.add_middleware(SlowAPIMiddleware)

    # Add custom exception handler for rate limit exceeded
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    logger.info(f"Rate limiting enabled: default={DEFAULT_RATE_LIMIT}")


# ==================== Rate Limit Decorators ====================


def rate_limit_chat():
    """Decorator for chat endpoints with stricter limits."""
    return limiter.limit(CHAT_RATE_LIMIT)


def rate_limit_ingest():
    """Decorator for ingestion endpoints with stricter limits."""
    return limiter.limit(INGEST_RATE_LIMIT)


def rate_limit_auth():
    """Decorator for auth endpoints to prevent brute force."""
    return limiter.limit(AUTH_RATE_LIMIT)


def rate_limit_custom(limit: str):
    """Decorator for custom rate limit.

    Args:
        limit: Rate limit string (e.g., "10/minute", "100/hour")
    """
    return limiter.limit(limit)


# ==================== Response Headers ====================


async def add_rate_limit_headers(
    request: Request, response: Response, limit: int, remaining: int, reset: int
) -> None:
    """Add rate limit headers to response.

    Args:
        request: FastAPI request.
        response: FastAPI response.
        limit: Maximum requests allowed.
        remaining: Requests remaining in window.
        reset: Seconds until limit resets.
    """
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)
