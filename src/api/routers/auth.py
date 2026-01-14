"""
Authentication router for login and token management.

Provides:
- /api/auth/login - Authenticate and get JWT token
- /api/auth/token/refresh - Refresh an existing token
- /api/auth/me - Get current user info
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..config import config
from ..middleware.auth import (
    create_access_token,
    refresh_token,
    get_current_user,
    User,
)
from ..middleware.rate_limiter import limiter
from src.utils.audit_logger import get_audit_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ==================== Request/Response Models ====================


class LoginRequest(BaseModel):
    """Login request body."""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    """Login response with token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: dict = Field(..., description="User information")


class TokenRefreshRequest(BaseModel):
    """Token refresh request body."""

    token: str = Field(..., description="Current valid JWT token")


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class UserResponse(BaseModel):
    """Current user information."""

    user_id: str
    role: str
    auth_method: str


# ==================== Simple User Store ====================
# In v2, this would be replaced with a proper database

# Simple in-memory user store for development
# Format: username -> (password_hash, role)
# In production, use a proper user database with hashed passwords
DEMO_USERS = {
    "admin": ("admin123", "admin"),
    "user": ("user123", "user"),
}


def verify_password(username: str, password: str) -> Optional[tuple]:
    """Verify username and password.

    For v1, uses simple in-memory store.
    In v2, use bcrypt with proper password hashing.

    Args:
        username: Username to verify.
        password: Password to verify.

    Returns:
        Tuple of (user_id, role) if valid, None otherwise.
    """
    if username in DEMO_USERS:
        stored_password, role = DEMO_USERS[username]
        if password == stored_password:
            return (username, role)
    return None


# ==================== Endpoints ====================


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # Prevent brute force attacks
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    """Authenticate user and return JWT token.

    Args:
        request: Login credentials.

    Returns:
        JWT token and user information.

    Raises:
        HTTPException: If credentials are invalid.
    """
    result = verify_password(body.username, body.password)
    client_ip = request.client.host if request.client else None
    audit = get_audit_logger()

    if not result:
        logger.warning(f"Failed login attempt for user: {body.username}")
        audit.log_login(
            user_id=body.username,
            ip_address=client_ip,
            success=False,
            error="Invalid credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id, role = result

    # Generate token
    access_token = create_access_token(user_id=user_id, role=role)
    expires_in = config.JWT_EXPIRATION_HOURS * 3600

    logger.info(f"User {user_id} logged in successfully")
    audit.log_login(user_id=user_id, ip_address=client_ip, success=True)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user={"user_id": user_id, "role": role},
    )


@router.post("/token/refresh", response_model=TokenRefreshResponse)
async def token_refresh(request: TokenRefreshRequest) -> TokenRefreshResponse:
    """Refresh an existing JWT token.

    Args:
        request: Current valid token.

    Returns:
        New JWT token with extended expiration.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    try:
        new_token = refresh_token(request.token)
        expires_in = config.JWT_EXPIRATION_HOURS * 3600

        return TokenRefreshResponse(
            access_token=new_token, token_type="bearer", expires_in=expires_in
        )
    except Exception as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user information.

    Args:
        user: Current authenticated user.

    Returns:
        User information.
    """
    return UserResponse(
        user_id=user.user_id, role=user.role, auth_method=user.auth_method
    )
