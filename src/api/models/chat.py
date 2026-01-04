"""Chat endpoint models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""

    query: str = Field(..., description="User's chat query")
    history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Conversation history"
    )
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = Field(None, description="Client session ID for memory context")
    skip_memory: bool = Field(
        default=False,
        description="Skip memory context retrieval for faster response (saves ~300ms)"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""

    response: str
    sources: List[Dict[str, Any]] = []
    query_type: str
    latency_ms: float
    graph_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
    model: Optional[str] = None
