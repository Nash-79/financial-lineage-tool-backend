"""Activity tracking middleware for API monitoring."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from fastapi import Request

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.responses import Response


async def activity_tracking_middleware(
    request: Request, call_next: RequestResponseEndpoint, state: Any
) -> Response:
    """Track all API requests for monitoring and analytics.

    Args:
        request: The incoming request.
        call_next: The next middleware or endpoint handler.
        state: Application state containing activity tracker.

    Returns:
        Response from the endpoint.

    Raises:
        Exception: Re-raises any exceptions after tracking them.
    """
    # Start timer
    start_time = time.time()

    # Process request
    try:
        response = await call_next(request)
        status = "success" if response.status_code < 400 else "error"

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Determine event type
        event_type = "health_check" if request.url.path == "/health" else "query"
        if "/ingest" in request.url.path:
            event_type = "ingest"
        elif response.status_code >= 400:
            event_type = "error"

        # Track the event
        if state.activity_tracker:
            metadata = {
                "method": request.method,
                "status_code": response.status_code,
                "query_params": dict(request.query_params),
            }

            await state.activity_tracker.track_event(
                event_type=event_type,
                endpoint=request.url.path,
                latency_ms=latency_ms,
                status=status,
                metadata=metadata,
            )

        return response

    except Exception as e:
        # Track error
        latency_ms = (time.time() - start_time) * 1000

        if state.activity_tracker:
            await state.activity_tracker.track_event(
                event_type="error",
                endpoint=request.url.path,
                latency_ms=latency_ms,
                status="error",
                metadata={
                    "method": request.method,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

        raise  # Re-raise the exception


def setup_activity_tracking(app: Any, state: Any) -> None:
    """Configure activity tracking middleware for the FastAPI application.

    Args:
        app: FastAPI application instance to configure.
        state: Application state containing activity tracker.
    """

    @app.middleware("http")
    async def _activity_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ):
        return await activity_tracking_middleware(request, call_next, state)
