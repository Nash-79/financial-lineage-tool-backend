"""
JWT Authentication Middleware for FastAPI.

Provides:
- JWT token verification and decoding
- Role-based access control (user/admin)
- API key authentication for service accounts
- Secure password hashing
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, Security, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel

from ..config import config

logger = logging.getLogger(__name__)

# Security schemes
# bearer_scheme = CustomHTTPBearer(auto_error=False) # Removed due to compatibility issues
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_bearer_token(authorization: Optional[str] = Header(None, alias="Authorization")) -> Optional[HTTPAuthorizationCredentials]:
    if not authorization:
        return None
    scheme, param = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer":
        return None
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=param)

async def get_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Optional[str]:
    return x_api_key


# ==================== Models ====================


class TokenPayload(BaseModel):
    """JWT token payload."""

    user_id: str
    role: str = "user"  # user, admin
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None


class User(BaseModel):
    """Authenticated user information."""

    user_id: str
    role: str
    auth_method: str = "jwt"  # jwt, api_key


# ==================== Token Functions ====================


def create_access_token(
    user_id: str, role: str = "user", expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token.

    Args:
        user_id: Unique user identifier.
        role: User role (user, admin).
        expires_delta: Custom expiration time.

    Returns:
        Encoded JWT token string.

    Raises:
        ValueError: If JWT_SECRET_KEY is not configured.
    """
    if not config.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY must be configured for token generation")

    if expires_delta is None:
        expires_delta = timedelta(hours=config.JWT_EXPIRATION_HOURS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "user_id": user_id,
        "role": role,
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> TokenPayload:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string.

    Returns:
        Decoded token payload.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    if not config.JWT_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not configured",
        )

    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
        return TokenPayload(**payload)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def refresh_token(token: str) -> str:
    """Refresh an access token if still valid.

    Args:
        token: Current JWT token.

    Returns:
        New JWT token with extended expiration.
    """
    payload = verify_token(token)
    return create_access_token(user_id=payload.user_id, role=payload.role)


# ==================== API Key Functions ====================


def verify_api_key(api_key: str) -> Optional[User]:
    """Verify an API key.

    For v1, we use a simple environment variable check.
    In v2, this would query a database of API keys.

    Args:
        api_key: The API key to verify.

    Returns:
        User object if valid, None otherwise.
    """
    # Simple API key validation using environment variable
    # In production, this would query a database
    valid_keys = {
        # Format: api_key -> (user_id, role)
        # Set via ADMIN_API_KEY env var for bootstrap access
    }

    admin_api_key = getattr(config, "ADMIN_API_KEY", None)
    if admin_api_key and api_key == admin_api_key:
        return User(user_id="api_admin", role="admin", auth_method="api_key")

    if api_key in valid_keys:
        user_id, role = valid_keys[api_key]
        return User(user_id=user_id, role=role, auth_method="api_key")

    return None


# ==================== Dependencies ====================


async def get_current_user(
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    api_key: Optional[str] = Depends(get_api_key),
) -> User:
    """Get current authenticated user.

    Supports both JWT bearer tokens and API keys.

    Args:
        bearer_token: Optional JWT bearer token.
        api_key: Optional API key header.

    Returns:
        Authenticated User object.

    Raises:
        HTTPException: If authentication fails.
    """
    # Check if auth is required
    jwt_required = getattr(config, "JWT_REQUIRED", False)

    # Try API key first
    if api_key:
        user = verify_api_key(api_key)
        if user:
            return user

    # Try JWT token
    if bearer_token:
        payload = verify_token(bearer_token.credentials)
        return User(user_id=payload.user_id, role=payload.role, auth_method="jwt")

    # No credentials provided
    if jwt_required or config.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In development mode, allow anonymous access
    return User(user_id="anonymous", role="user", auth_method="anonymous")


async def get_current_user_optional(
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    api_key: Optional[str] = Depends(get_api_key),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.

    Use this for endpoints that have different behavior for
    authenticated vs anonymous users.
    """
    try:
        # Try API key first
        if api_key:
            user = verify_api_key(api_key)
            if user:
                return user

        # Try JWT token
        if bearer_token:
            payload = verify_token(bearer_token.credentials)
            return User(user_id=payload.user_id, role=payload.role, auth_method="jwt")

        return None

    except HTTPException:
        return None


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role for endpoint access.

    Args:
        user: Authenticated user.

    Returns:
        User if admin.

    Raises:
        HTTPException: If user is not admin.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user


# ==================== Utility Functions ====================


def is_public_endpoint(path: str) -> bool:
    """Check if an endpoint is public (no auth required).

    Args:
        path: Request path.

    Returns:
        True if public, False otherwise.
    """
    public_paths = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login",
        "/api/auth/register",
    }

    # Exact match
    if path in public_paths:
        return True

    # Prefix match for static files
    if path.startswith("/static/"):
        return True

    return False
