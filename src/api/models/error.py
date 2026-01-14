"""
Standard error response models.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: str = Field(..., description="Error code or type")
    message: str = Field(..., description="Human-readable error message")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error context"
    )
