"""Lineage endpoint models."""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field


class LineageQueryRequest(BaseModel):
    """Request model for lineage queries."""

    question: str = Field(..., description="Natural language question")


class LineageResponse(BaseModel):
    """Response model for lineage queries."""

    question: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    graph_entities: List[str] = Field(default_factory=list)
    confidence: float


class EdgeReviewRequest(BaseModel):
    """Request model for reviewing lineage edges."""

    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Relationship type")
    action: str = Field(..., pattern="^(approve|reject)$", description="Review action")
    reviewer_notes: str = Field("", description="Optional reviewer notes")


class EdgeReviewResponse(BaseModel):
    """Response model for edge review."""

    success: bool
    message: str
    updated_edge: dict = Field(default_factory=dict)


class LineageInferenceRequest(BaseModel):
    """Request model for LLM-based lineage inference."""

    scope: str = Field(
        ..., description="File path or scope identifier for context retrieval"
    )
    project_id: Optional[str] = Field(
        None, description="Optional project ID to filter context"
    )
    max_nodes: int = Field(
        20, ge=1, le=100, description="Maximum graph nodes to include in context"
    )
    max_chunks: int = Field(
        10, ge=1, le=50, description="Maximum code chunks to include in context"
    )


class LineageInferenceResponse(BaseModel):
    """Response model for lineage inference."""

    success: bool
    message: str
    context_nodes_count: int
    proposals_count: int
    proposals: List[Dict[str, Any]] = Field(default_factory=list)


# Rebuild models to resolve forward references from PEP 563 (from __future__ import annotations)
LineageQueryRequest.model_rebuild()
LineageResponse.model_rebuild()
EdgeReviewRequest.model_rebuild()
EdgeReviewResponse.model_rebuild()
LineageInferenceRequest.model_rebuild()
LineageInferenceResponse.model_rebuild()
