"""API middleware components."""

from __future__ import annotations

from .activity import setup_activity_tracking
from .auth import (
    get_current_user,
    get_current_user_optional,
    require_admin,
    create_access_token,
    verify_token,
    User,
)
from .cors import setup_cors
from .error_handler import setup_error_handlers
from .rate_limiter import (
    setup_rate_limiting,
    limiter,
    rate_limit_chat,
    rate_limit_ingest,
    rate_limit_auth,
    rate_limit_custom,
)

__all__ = [
    "setup_cors",
    "setup_activity_tracking",
    "setup_error_handlers",
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "create_access_token",
    "verify_token",
    "User",
    "setup_rate_limiting",
    "limiter",
    "rate_limit_chat",
    "rate_limit_ingest",
    "rate_limit_auth",
    "rate_limit_custom",
]
