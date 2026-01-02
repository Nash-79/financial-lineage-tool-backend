"""API middleware components."""

from __future__ import annotations

from .activity import setup_activity_tracking
from .cors import setup_cors
from .error_handler import setup_error_handlers

__all__ = ["setup_cors", "setup_activity_tracking", "setup_error_handlers"]
