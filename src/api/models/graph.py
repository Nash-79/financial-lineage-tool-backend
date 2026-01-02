"""Knowledge graph models."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class EntityRequest(BaseModel):
    """Request model for creating graph entities."""

    entity_id: str
    entity_type: str
    name: str
    properties: Dict[str, Any] = {}


class RelationshipRequest(BaseModel):
    """Request model for creating graph relationships."""

    source_id: str
    target_id: str
    relationship_type: str
    properties: Dict[str, Any] = {}
