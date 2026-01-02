"""
Global exception handling middleware.
"""

import logging
import uuid
from typing import Callable, Union

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..models.error import ErrorResponse

logger = logging.getLogger(__name__)


def setup_error_handlers(app: FastAPI):
    """
    Register global exception handlers.
    
    Handles:
    - HTTP Exceptions (FastAPI/Starlette)
    - Validation Errors (Pydantic)
    - Unhandled Server Errors
    """
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle standard HTTP exceptions."""
        return _create_error_response(
            status_code=exc.status_code,
            error=str(exc.status_code),
            message=str(exc.detail),
            request_id=getattr(request.state, "request_id", None)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        return _create_error_response(
            status_code=422,
            error="validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
            request_id=getattr(request.state, "request_id", None)
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle catch-all unhandled exceptions."""
        error_id = uuid.uuid4().hex
        logger.error(f"Unhandled exception {error_id}: {exc}", exc_info=True)
        
        return _create_error_response(
            status_code=500,
            error="internal_server_error",
            message="An internal server error occurred.",
            details={"error_id": error_id}, # Only show ID in production
            request_id=getattr(request.state, "request_id", None)
        )
    
    # Add middleware to ensure request_id exists if not already present
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        if not hasattr(request.state, "request_id"):
             request.state.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        return await call_next(request)


def _create_error_response(
    status_code: int,
    error: str,
    message: str,
    details: dict = None,
    request_id: str = None
) -> JSONResponse:
    """Create standardized JSON error response."""
    content = ErrorResponse(
        error=error,
        message=message,
        details=details,
        request_id=request_id
    ).model_dump(exclude_none=True)
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )
