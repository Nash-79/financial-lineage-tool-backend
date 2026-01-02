"""Lineage endpoint models."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class LineageQueryRequest(BaseModel):
    """Request model for lineage queries."""

    question: str = Field(..., description="Natural language question")


class LineageResponse(BaseModel):
    """Response model for lineage queries."""

    question: str
    answer: str
    sources: List[str] = []
    graph_entities: List[str] = []
    confidence: float
