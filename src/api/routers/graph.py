"""Knowledge graph management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from fastapi import APIRouter, HTTPException

from ..models.graph import EntityRequest, RelationshipRequest

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


def get_app_state() -> Any:
    """Get application state from FastAPI app.

    This is a placeholder that will be replaced with actual state injection.
    The state will be passed via dependency injection in main.py.
    """
    # This will be replaced with proper dependency injection
    from ..main_local import state

    return state


@router.get("/stats")
async def get_graph_stats() -> Dict[str, Any]:
    """Get knowledge graph statistics.

    Returns statistics about the graph including node counts by type,
    relationship counts, and other metadata.

    Returns:
        Dictionary containing graph statistics.
    """
    state = get_app_state()
    return state.graph.get_stats()


@router.post("/entity")
async def add_entity(request: EntityRequest) -> Dict[str, str]:
    """Add an entity to the knowledge graph.

    Creates a new node in the graph with the specified type and properties.

    Args:
        request: Entity request with ID, type, name, and properties.

    Returns:
        Dictionary with creation status and entity ID.
    """
    state = get_app_state()

    state.graph.add_entity(
        entity_id=request.entity_id,
        entity_type=request.entity_type,
        name=request.name,
        **request.properties,
    )
    return {"status": "created", "entity_id": request.entity_id}


@router.post("/relationship")
async def add_relationship(request: RelationshipRequest) -> Dict[str, str]:
    """Add a relationship to the knowledge graph.

    Creates a new edge between two nodes with the specified type and properties.

    Args:
        request: Relationship request with source ID, target ID, type, and properties.

    Returns:
        Dictionary with creation status.
    """
    state = get_app_state()

    state.graph.add_relationship(
        source_id=request.source_id,
        target_id=request.target_id,
        relationship_type=request.relationship_type,
        **request.properties,
    )
    return {"status": "created"}


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str) -> Dict[str, Any]:
    """Get an entity by ID.

    Retrieves a single entity from the graph by its unique identifier.

    Args:
        entity_id: Unique identifier of the entity.

    Returns:
        Dictionary containing entity data.

    Raises:
        HTTPException: If entity is not found.
    """
    state = get_app_state()

    entity = state.graph.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/search")
async def search_entities(name: str) -> List[Dict[str, Any]]:
    """Search entities by name.

    Performs a search on entity names to find matching nodes.

    Args:
        name: Name or partial name to search for.

    Returns:
        List of entities matching the search query.
    """
    state = get_app_state()
    return state.graph.find_by_name(name)


@router.get("/lineage/{entity_id}")
async def get_lineage(
    entity_id: str, direction: str = "both", max_depth: int = 5
) -> Dict[str, Any]:
    """Get lineage for an entity.

    Retrieves upstream and/or downstream lineage for the specified entity.

    Args:
        entity_id: ID of the entity to get lineage for.
        direction: Direction of lineage (upstream, downstream, or both).
        max_depth: Maximum traversal depth (default: 5).

    Returns:
        Dictionary with entity_id and upstream/downstream lineage.
    """
    state = get_app_state()

    result: Dict[str, Any] = {"entity_id": entity_id}

    if direction in ["upstream", "both"]:
        result["upstream"] = state.graph.get_upstream(entity_id, max_depth)

    if direction in ["downstream", "both"]:
        result["downstream"] = state.graph.get_downstream(entity_id, max_depth)

    return result
