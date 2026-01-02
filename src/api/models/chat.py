"""Chat endpoint models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""

    query: str = Field(..., description="User's chat query")
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""

    response: str
    sources: List[Dict[str, Any]] = []
    query_type: str
    latency_ms: float
