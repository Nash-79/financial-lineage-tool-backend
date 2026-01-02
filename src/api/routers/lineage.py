"""Lineage query and graph traversal endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.lineage import LineageQueryRequest, LineageResponse

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/v1/lineage", tags=["lineage"])


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


@router.post("/query", response_model=LineageResponse)
async def query_lineage(
    request: LineageQueryRequest,
    project_id: Optional[str] = Query(None, description="Project ID context"),
) -> LineageResponse:
    """Query data lineage using natural language.

    Uses the agent to interpret natural language questions about
    data lineage and return structured answers with sources.

    Args:
        request: Lineage query request with natural language question.
        project_id: Optional project context for the query.

    Returns:
        LineageResponse with answer, sources, graph entities, and confidence.
    """
    state = get_app_state()

    if not state.agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # TODO: Pass project_id to agent context
    result = await state.agent.query(request.question)

    return LineageResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result.get("sources", []),
        graph_entities=result.get("graph_entities", []),
        confidence=result["confidence"],
    )


@router.get("/nodes")
async def get_lineage_nodes(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    repo_ids: Optional[str] = Query(
        None, description="Comma-separated list of repository IDs"
    ),
    include_linked: bool = Query(
        False, description="Include nodes from linked repositories"
    ),
    type: Optional[str] = Query(None, description="Filter by node type"),
    search: Optional[str] = Query(None, description="Search term for node names"),
) -> Dict[str, Any]:
    """Get lineage nodes from the knowledge graph.

    Args:
        project_id: Filter by project ID
        repo_ids: Filter by repository IDs
        include_linked: Include linked repositories (not implemented yet)
        type: Filter by node type
        search: Search term

    Returns:
        Dictionary with nodes list and total count.
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    try:
        # Build query
        where_clauses = []
        params = {}

        if project_id:
            where_clauses.append("n.project_id = $project_id")
            params["project_id"] = project_id

        if repo_ids:
            repo_id_list = [rid.strip() for rid in repo_ids.split(",") if rid.strip()]
            if repo_id_list:
                where_clauses.append("n.repository_id IN $repo_ids")
                params["repo_ids"] = repo_id_list

        if type:
            where_clauses.append(f"n:{type}")

        if search:
            where_clauses.append("toLower(n.name) CONTAINS toLower($search)")
            params["search"] = search

        where_stmt = (
            "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        )

        query = f"""
        MATCH (n)
        {where_stmt}
        RETURN n, labels(n) as labels
        LIMIT 1000
        """

        results = state.graph._execute_query(query, params)

        nodes = []
        for record in results:
            node_data = record["n"]
            labels = record["labels"]
            nodes.append(
                {
                    "id": node_data.get("id"),
                    "entity_type": labels[0] if labels else "Unknown",
                    **node_data,
                }
            )

        return {"nodes": nodes, "total": len(nodes)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nodes: {e}")


@router.get("/edges")
async def get_lineage_edges(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
) -> Dict[str, Any]:
    """Get lineage edges (relationships) from the knowledge graph.

    Args:
        project_id: Filter by project ID (both source and target must be in project)

    Returns:
        Dictionary with edges list and total count.
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    try:
        where_stmt = ""
        params = {}

        if project_id:
            where_stmt = "WHERE source.project_id = $project_id AND target.project_id = $project_id"
            params["project_id"] = project_id

        query = f"""
        MATCH (source)-[r]->(target)
        {where_stmt}
        RETURN
            source.id as source,
            type(r) as type,
            target.id as target,
            properties(r) as metadata
        LIMIT 1000
        """

        results = state.graph._execute_query(query, params)

        edges = []
        for record in results:
            edges.append(
                {
                    "id": record.get("metadata", {}).get("id"),  # Edges might not have IDs
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"],
                    **record.get("metadata", {}),
                }
            )

        return {"edges": edges, "total": len(edges)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch edges: {e}")


@router.get("/search")
async def search_lineage(
    q: str = Query(..., description="Search query"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
) -> Dict[str, Any]:
    """Search lineage by entity name or query.

    Args:
        q: Search query string.
        project_id: Filter by project ID.

    Returns:
        Dictionary with nodes and edges matching the search query.
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    try:
        results = state.graph.find_by_name(q, project_id=project_id)

        nodes = []
        for result in results:
            nodes.append(
                {
                    "id": result.get("id", ""),
                    "label": result.get("name", ""),
                    "type": result.get("entity_type", "table").lower(),
                    "metadata": result,
                }
            )

        return {"nodes": nodes, "edges": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/node/{node_id}")
async def get_node_lineage(
    node_id: str,
    direction: str = Query("both", pattern="^(upstream|downstream|both)$"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    cross_repository: bool = Query(True, description="Traverse across repositories"),
) -> Dict[str, Any]:
    """Get lineage for a specific node.

    Args:
        node_id: ID of the node to get lineage for.
        direction: Direction of lineage traversal.
        project_id: Filter traversal to project.
        cross_repository: Allow crossing repository boundaries.

    Returns:
        Dictionary with nodes and edges representing the lineage.
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    try:
        nodes = []
        edges = []

        # Get the node itself
        entity = state.graph.get_entity(node_id)
        if entity:
            nodes.append(
                {
                    "id": entity.get("id", ""),
                    "label": entity.get("name", ""),
                    "type": entity.get("entity_type", "table").lower(),
                    "metadata": entity,
                }
            )

        # Build repository filter
        repo_ids = None
        if not cross_repository and entity and entity.get("repository_id"):
            repo_ids = [entity["repository_id"]]

        # Get upstream/downstream based on direction
        if direction in ["upstream", "both"]:
            upstream = state.graph.get_upstream(
                node_id, max_depth=5, project_id=project_id, repo_ids=repo_ids
            )
            for item in upstream:
                nodes.append(
                    {
                        "id": item["source"],  # Source is upstream
                        "label": item.get("source_data", {}).get("name", ""),
                        "type": "unknown",  # Type not returned by query explicitly
                        "metadata": item.get("source_data", {}),
                    }
                )
                edges.append(
                    {
                        "source": item["source"],
                        "target": item["target"],
                        "type": item["relationship"],
                    }
                )

        if direction in ["downstream", "both"]:
            downstream = state.graph.get_downstream(
                node_id, max_depth=5, project_id=project_id, repo_ids=repo_ids
            )
            for item in downstream:
                nodes.append(
                    {
                        "id": item["target"],  # Target is downstream
                        "label": item.get("target_data", {}).get("name", ""),
                        "type": "unknown",
                        "metadata": item.get("target_data", {}),
                    }
                )
                edges.append(
                    {
                        "source": item["source"],
                        "target": item["target"],
                        "type": item["relationship"],
                    }
                )

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch lineage: {e}")
