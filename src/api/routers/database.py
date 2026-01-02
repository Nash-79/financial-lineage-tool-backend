"""
Database router for schema browsing.

Provides endpoints for querying database schema information from Neo4j.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/database", tags=["database"])


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state
    return state


@router.get("/schemas")
async def get_schemas(
    schema: Optional[str] = Query(None, description="Filter by schema name"),
) -> Dict[str, Any]:
    """
    Get database schemas and their tables from Neo4j.

    Queries Neo4j for all Schema entities and their associated tables.

    Args:
        schema: Optional schema name to filter by.

    Returns:
        Dictionary with schemas and their table counts.
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph database not initialized")

    try:
        # Build Cypher query
        if schema:
            # Filter by specific schema
            query = """
                MATCH (s:Schema {name: $schema_name})
                OPTIONAL MATCH (s)-[:CONTAINS]->(t:Table)
                WITH s, collect(t) as tables
                RETURN s.name as schema_name,
                       s.description as description,
                       size(tables) as table_count,
                       [t IN tables | {name: t.name, type: 'table'}] as tables
            """
            params = {"schema_name": schema}
        else:
            # Get all schemas
            query = """
                MATCH (s:Schema)
                OPTIONAL MATCH (s)-[:CONTAINS]->(t:Table)
                WITH s, collect(t) as tables
                RETURN s.name as schema_name,
                       s.description as description,
                       size(tables) as table_count,
                       [t IN tables | {name: t.name, type: 'table'}] as tables
                ORDER BY s.name
            """
            params = {}

        # Execute query
        with state.graph.driver.session(database=state.graph.database) as session:
            result = session.run(query, params)
            records = list(result)

        # Format response
        schemas = []
        for record in records:
            schemas.append({
                "name": record["schema_name"],
                "description": record["description"],
                "table_count": record["table_count"],
                "tables": record["tables"] or [],
            })

        return {
            "total": len(schemas),
            "schemas": schemas,
        }

    except Exception as e:
        logger.error(f"Failed to query schemas: {e}")
        # Return empty result if graph has no schemas
        if "not found" in str(e).lower() or "no data" in str(e).lower():
            return {
                "total": 0,
                "schemas": [],
            }
        raise HTTPException(status_code=500, detail=f"Failed to query schemas: {str(e)}")
