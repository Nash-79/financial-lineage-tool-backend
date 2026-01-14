"""Models for inference outputs."""

from pydantic import BaseModel, Field


class LineageEdgeProposal(BaseModel):
    """Structured lineage edge proposal from LLM."""

    source_node: str = Field(..., description="Source entity identifier")
    target_node: str = Field(..., description="Target entity identifier")
    relationship_type: str = Field(..., description="Relationship type (READS|WRITES)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    reasoning: str = Field("", description="Short explanation for the edge")
