"""Lineage query and graph traversal endpoints."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.utils.urn import is_valid_urn, parse_urn

from ..models.lineage import (
    EdgeReviewRequest,
    EdgeReviewResponse,
    LineageQueryRequest,
    LineageResponse,
    LineageInferenceRequest,
    LineageInferenceResponse,
)

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/v1/lineage", tags=["lineage"])


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


def _parse_edge_asset_path(asset_path: str) -> Optional[Dict[str, str]]:
    if "/" not in asset_path:
        return None
    rel_type, rest = asset_path.split("/", 1)
    if "->" not in rest or ":" not in rest:
        return None
    source_part, target_part = rest.split("->", 1)
    if ":" not in source_part or ":" not in target_part:
        return None
    source_label, source_name = source_part.split(":", 1)
    target_label, target_name = target_part.split(":", 1)
    return {
        "rel_type": rel_type,
        "source_label": source_label,
        "source_name": source_name,
        "target_label": target_label,
        "target_name": target_name,
    }


def _is_safe_label(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_]+$", value))


def _resolve_node_urn(
    state: Any, urn: str, project_id_override: Optional[str]
) -> Optional[str]:
    parts = parse_urn(urn)
    if parts["entity_type"] != "neo4j-node":
        return None
    if "/" not in parts["asset_path"]:
        return None
    label, name = parts["asset_path"].split("/", 1)
    if not _is_safe_label(label):
        return None
    project_id = project_id_override or parts["project_id"]
    query = """
    MATCH (n)
    WHERE $label IN labels(n)
      AND toLower(n.name) = toLower($name)
      AND (n.project_id = $project_id OR $project_id IS NULL)
    RETURN n
    LIMIT 1
    """
    results = state.graph._execute_query(
        query, {"label": label, "name": name, "project_id": project_id}
    )
    if not results:
        return None
    node_data = results[0]["n"]
    return node_data.get("id")


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

    # Validate type parameter before try block
    if type:
        if not isinstance(type, str) or type.isdigit():
            raise HTTPException(
                status_code=422,
                detail="Type parameter must be a valid node label (e.g., 'Table', 'Column', 'View')",
            )

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

        where_stmt = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

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
    status: Optional[str] = Query(
        None, description="Filter by edge status (approved/pending_review/rejected)"
    ),
    min_confidence: Optional[float] = Query(
        None, description="Minimum confidence score (0.0-1.0)"
    ),
    source: Optional[str] = Query(
        None, description="Filter by edge source (parser/ollama_llm/human)"
    ),
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
        where_clauses = []
        params = {}

        if project_id:
            where_clauses.append(
                "source.project_id = $project_id AND target.project_id = $project_id"
            )
            params["project_id"] = project_id

        if status:
            where_clauses.append("r.status = $status")
            params["status"] = status

        if min_confidence is not None:
            where_clauses.append("r.confidence >= $min_confidence")
            params["min_confidence"] = min_confidence

        if source:
            where_clauses.append("r.source = $source")
            params["source"] = source

        where_stmt = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

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
            # Extract metadata and rename 'source' to 'edge_source' to avoid
            # overwriting the node source ID with the relationship provenance
            meta = dict(record.get("metadata", {}) or {})
            edge_source = meta.pop(
                "source", None
            )  # e.g., 'parser', 'ollama_llm', 'human'

            edges.append(
                {
                    "id": meta.get("id"),
                    "source": record["source"],  # Node ID
                    "target": record["target"],  # Node ID
                    "type": record["type"],
                    "edge_source": edge_source,  # Relationship provenance
                    **meta,
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


@router.post("/review", response_model=EdgeReviewResponse)
async def review_edge(request: EdgeReviewRequest) -> EdgeReviewResponse:
    """Review and approve/reject a lineage edge.

    Allows manual review of LLM-inferred edges or any edge in the graph.
    Updates the edge status based on the review action.

    Args:
        request: Edge review request with source, target, relationship type, and action

    Returns:
        EdgeReviewResponse indicating success/failure and updated edge metadata
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    try:
        # Verify edge exists
        check_query = """
        MATCH (source {id: $source_id})-[r]->(target {id: $target_id})
        WHERE type(r) = $relationship_type
        RETURN r, properties(r) as props
        """

        existing = state.graph._execute_query(
            check_query,
            {
                "source_id": request.source_id,
                "target_id": request.target_id,
                "relationship_type": request.relationship_type,
            },
        )

        if not existing or len(existing) == 0:
            return EdgeReviewResponse(
                success=False, message="Edge not found", updated_edge={}
            )

        # Update edge status based on action
        new_status = "approved" if request.action == "approve" else "rejected"

        update_query = """
        MATCH (source {id: $source_id})-[r]->(target {id: $target_id})
        WHERE type(r) = $relationship_type
        SET r.status = $status,
            r.reviewed_at = datetime(),
            r.reviewer_notes = $reviewer_notes
        RETURN properties(r) as props
        """

        state.graph._execute_write(
            update_query,
            {
                "source_id": request.source_id,
                "target_id": request.target_id,
                "relationship_type": request.relationship_type,
                "status": new_status,
                "reviewer_notes": request.reviewer_notes,
            },
        )

        return EdgeReviewResponse(
            success=True,
            message=f"Edge {request.action}d successfully",
            updated_edge={
                "source": request.source_id,
                "target": request.target_id,
                "type": request.relationship_type,
                "status": new_status,
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review failed: {e}")


@router.post("/infer", response_model=LineageInferenceResponse)
async def infer_lineage(request: LineageInferenceRequest) -> LineageInferenceResponse:
    """Trigger LLM-based lineage inference for a given scope.

    Retrieves context (graph + code), asks LLM to propose edges,
    and returns the proposals. Proposals are auto-ingested as 'pending_review'.

    Args:
        request: Inference request with scope and limits.

    Returns:
        LineageInferenceResponse with generated proposals.
    """
    state = get_app_state()

    if not state.inference_service:
        raise HTTPException(
            status_code=503, detail="Lineage Inference Service not initialized"
        )

    try:
        # 1. Retrieve Context
        context = await state.inference_service.retrieve_context(
            scope=request.scope,
            max_nodes=request.max_nodes,
            max_chunks=request.max_chunks,
            project_id=request.project_id,
        )

        node_count = len(context.get("nodes", []))

        # 2. Propose Edges
        # Define edge types we are interested in (could be parameterized later)
        edge_types = ["DEPENDS_ON", "CALLS", "READS_FROM", "WRITES_TO"]

        proposals = await state.inference_service.propose_edges(
            context=context, edge_types=edge_types
        )

        # 3. Ingest Proposals
        if proposals:
            state.inference_service.ingest_proposals(
                proposals=proposals, default_status="pending_review"
            )

        return LineageInferenceResponse(
            success=True,
            message=f"Inference complete. Generated {len(proposals)} proposals.",
            context_nodes_count=node_count,
            proposals_count=len(proposals),
            proposals=proposals,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")


@router.get("/node/{node_id:path}")
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

        if is_valid_urn(node_id):
            resolved = _resolve_node_urn(state, node_id, project_id)
            if not resolved:
                raise HTTPException(status_code=404, detail="Node not found for URN")
            node_id = resolved

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


@router.get("/edge/{edge_urn:path}")
async def get_edge_detail(edge_urn: str) -> Dict[str, Any]:
    """Resolve a lineage edge from a URN."""
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    if not is_valid_urn(edge_urn):
        raise HTTPException(status_code=422, detail="Invalid edge URN")

    parts = parse_urn(edge_urn)
    if parts["entity_type"] != "neo4j-edge":
        raise HTTPException(status_code=422, detail="URN is not a neo4j-edge")

    parsed = _parse_edge_asset_path(parts["asset_path"])
    if not parsed:
        raise HTTPException(status_code=422, detail="Invalid edge URN asset path")

    if not all(
        _is_safe_label(value)
        for value in [
            parsed["rel_type"],
            parsed["source_label"],
            parsed["target_label"],
        ]
    ):
        raise HTTPException(status_code=422, detail="Invalid edge URN labels")

    query = f"""
    MATCH (source)-[r:{parsed['rel_type']}]->(target)
    WHERE $source_label IN labels(source)
      AND $target_label IN labels(target)
      AND toLower(source.name) = toLower($source_name)
      AND toLower(target.name) = toLower($target_name)
      AND (source.project_id = $project_id OR $project_id IS NULL)
      AND (target.project_id = $project_id OR $project_id IS NULL)
    RETURN source, target, labels(source) as source_labels, labels(target) as target_labels,
           properties(r) as metadata, type(r) as rel_type
    LIMIT 1
    """

    results = state.graph._execute_query(
        query,
        {
            "source_label": parsed["source_label"],
            "target_label": parsed["target_label"],
            "source_name": parsed["source_name"],
            "target_name": parsed["target_name"],
            "project_id": parts["project_id"],
        },
    )

    if not results:
        raise HTTPException(status_code=404, detail="Edge not found for URN")

    record = results[0]
    source_node = record["source"]
    target_node = record["target"]

    return {
        "edge": {
            "type": record.get("rel_type"),
            "metadata": record.get("metadata", {}),
            "source": {
                "id": source_node.get("id"),
                "label": source_node.get("name"),
                "type": (record.get("source_labels") or ["Unknown"])[0],
                "metadata": dict(source_node),
            },
            "target": {
                "id": target_node.get("id"),
                "label": target_node.get("name"),
                "type": (record.get("target_labels") or ["Unknown"])[0],
                "metadata": dict(target_node),
            },
        }
    }
