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
    session_id: Optional[str] = Field(
        None, description="Client session ID for memory context"
    )
    skip_memory: bool = Field(
        default=False,
        description="Skip memory context retrieval for faster response (saves ~300ms)",
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""

    response: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    query_type: str
    latency_ms: float
    model: Optional[str] = None
    next_actions: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    graph_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
    message_id: Optional[str] = Field(
        None, description="Unique message identifier for artifact retrieval"
    )


class ChatGraphArtifactResponse(BaseModel):
    """Response model for chat graph artifact retrieval."""

    session_id: str
    message_id: str
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatGraphArtifactNotFoundResponse(BaseModel):
    """Response model for missing chat graph artifacts."""

    error: str = "Graph artifact not found"
    session_id: str
    message_id: str
    suggestion: str = "Use the current lineage page for historical analysis"
