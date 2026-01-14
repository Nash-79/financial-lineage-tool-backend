"""
Database router for schema browsing.

Provides endpoints for querying database schema information from Neo4j.
"""

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.storage.duckdb_client import get_duckdb_client
from src.utils.audit_logger import get_audit_logger
from ..middleware.auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/database",
    tags=["database"],
    dependencies=[Depends(get_current_user)],
)


# Query request/response models
class QueryRequest(BaseModel):
    """Database query request model."""

    sql: str = Field(..., description="SQL query to execute")
    snapshot_id: Optional[str] = Field(
        None, description="Snapshot ID to query (leave empty for live database)"
    )


class QueryResponse(BaseModel):
    """Database query response model."""

    columns: List[str]
    rows: List[List[Any]]
    row_count: int


# SQL validation constants
ALLOWED_KEYWORDS = {"SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"}
FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "CALL",
}


def validate_sql(sql: str) -> None:
    """
    Validate SQL query to ensure it's read-only.

    Args:
        sql: SQL query to validate

    Raises:
        HTTPException: If query contains forbidden keywords
    """
    sql_upper = sql.upper()

    # Remove comments
    sql_upper = re.sub(r"--.*?\n", " ", sql_upper)
    sql_upper = re.sub(r"/\*.*?\*/", " ", sql_upper, flags=re.DOTALL)

    # Check for forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(r"\b" + keyword + r"\b", sql_upper):
            raise HTTPException(
                status_code=400,
                detail=f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed.",
            )

    # Check that query starts with an allowed keyword
    first_word = sql_upper.strip().split()[0] if sql_upper.strip() else ""
    if first_word not in ALLOWED_KEYWORDS:
        raise HTTPException(
            status_code=400,
            detail=f"Query must start with one of: {', '.join(ALLOWED_KEYWORDS)}",
        )


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


def _format_table_name(record: Any) -> str:
    """Combine schema and table name into a dotted identifier."""
    schema = record.get("schema_name") or record.get("schema") or ""
    table = record.get("table_name") or record.get("table") or ""
    return f"{schema}.{table}" if schema else table


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
            schemas.append(
                {
                    "name": record["schema_name"],
                    "description": record["description"],
                    "table_count": record["table_count"],
                    "tables": record["tables"] or [],
                }
            )

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
        raise HTTPException(
            status_code=500, detail=f"Failed to query schemas: {str(e)}"
        )


@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest, user: User = Depends(get_current_user)):
    """
    Execute a SQL query against the DuckDB database.

    Can query either the live in-memory database or a specific snapshot.
    Only SELECT queries are allowed for safety.

    Args:
        request: Query request containing SQL and optional snapshot_id

    Returns:
        Query results with columns, rows, and row count

    Raises:
        HTTPException: If query is invalid, forbidden, or execution fails
    """
    try:
        # Validate SQL query
        validate_sql(request.sql)

        if request.snapshot_id:
            # Query snapshot database
            logger.info(f"Executing query on snapshot {request.snapshot_id}")
            result = await _execute_on_snapshot(request.sql, request.snapshot_id)
        else:
            # Query live database
            logger.info("Executing query on live database")
            result = await _execute_on_live(request.sql)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
    finally:
        try:
            audit = get_audit_logger()
            audit.log_query(
                user_id=user.user_id,
                query_type="database",
                query_hash=hashlib.sha256(request.sql.encode()).hexdigest(),
                latency_ms=None,
            )
        except Exception:
            pass


async def _execute_on_live(sql: str) -> QueryResponse:
    """
    Execute query on live in-memory database.

    Args:
        sql: SQL query to execute

    Returns:
        Query results
    """
    duckdb_client = get_duckdb_client()

    if not duckdb_client.conn:
        raise HTTPException(status_code=500, detail="Database connection not available")

    try:
        return await _execute_query_with_timeout(duckdb_client.conn, sql)
    except duckdb.Error as e:
        logger.error(f"DuckDB error: {e}")
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")


async def _execute_on_snapshot(sql: str, snapshot_id: str) -> QueryResponse:
    """
    Execute query on a specific snapshot.

    Args:
        sql: SQL query to execute
        snapshot_id: Snapshot ID to query

    Returns:
        Query results
    """
    duckdb_client = get_duckdb_client()

    if not duckdb_client.snapshot_manager:
        raise HTTPException(
            status_code=400, detail="Snapshots not enabled (running in persistent mode)"
        )

    # Get snapshot path
    snapshots = duckdb_client.snapshot_manager.list_snapshots()
    snapshot = next((s for s in snapshots if s["id"] == snapshot_id), None)

    if not snapshot:
        raise HTTPException(
            status_code=404, detail=f"Snapshot not found: {snapshot_id}"
        )

    # Create read-only connection to snapshot
    snapshot_path = snapshot["file_path"]
    snapshot_conn = None

    try:
        # Load snapshot into temporary in-memory connection
        snapshot_conn = duckdb.connect(":memory:", read_only=False)
        snapshot_conn.execute(f"IMPORT DATABASE '{snapshot_path}'")

        return await _execute_query_with_timeout(snapshot_conn, sql)

    except duckdb.Error as e:
        logger.error(f"DuckDB error on snapshot: {e}")
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")
    finally:
        # Always close snapshot connection
        if snapshot_conn:
            try:
                snapshot_conn.close()
            except:
                pass


async def _execute_query_with_timeout(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
) -> QueryResponse:
    """Execute a DuckDB query with a timeout and return a response model."""
    try:
        try:
            conn.execute(f"SET statement_timeout='{QUERY_TIMEOUT_SECONDS}s'")
        except Exception:
            try:
                conn.execute(f"PRAGMA statement_timeout='{QUERY_TIMEOUT_SECONDS}s'")
            except Exception:
                logger.debug("DuckDB statement_timeout not supported on this version")

        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description] if result.description else []
        rows = result.fetchall()
        rows_list = [list(row) for row in rows]
        return QueryResponse(
            columns=columns,
            rows=rows_list,
            row_count=len(rows_list),
        )
    except duckdb.Error as e:
        if "timeout" in str(e).lower():
            raise HTTPException(
                status_code=408,
                detail=f"Query timed out after {QUERY_TIMEOUT_SECONDS} seconds",
            )
        raise


QUERY_TIMEOUT_SECONDS = 30


@router.get("/tables/{schema_name}/{table_name}/dependencies")
async def get_table_dependencies(
    schema_name: str,
    table_name: str,
) -> Dict[str, List[str]]:
    """
    Return upstream/downstream table dependencies from Neo4j lineage graph.

    Upstream: tables that the current table references.
    Downstream: tables that depend on the current table.
    """
    state = get_app_state()
    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph database not initialized")

    try:
        with state.graph.driver.session(database=state.graph.database) as session:
            result = session.run(
                """
                MATCH (s:Schema {name: $schema_name})-[:CONTAINS]->(t:Table {name: $table_name})
                OPTIONAL MATCH (t)-[:REFERENCES]->(up:Table)<-[:CONTAINS]-(up_s:Schema)
                OPTIONAL MATCH (down:Table)-[:REFERENCES]->(t)<-[:CONTAINS]-(down_s:Schema)
                RETURN
                    collect(DISTINCT {schema_name: coalesce(up_s.name, ''), table_name: up.name}) AS upstream,
                    collect(DISTINCT {schema_name: coalesce(down_s.name, ''), table_name: down.name}) AS downstream
                """,
                {"schema_name": schema_name, "table_name": table_name},
            )
            record = result.single()
            upstream_raw = record["upstream"] if record and "upstream" in record else []
            downstream_raw = (
                record["downstream"] if record and "downstream" in record else []
            )

        upstream = [
            _format_table_name(item) for item in upstream_raw if item.get("table_name")
        ]
        downstream = [
            _format_table_name(item)
            for item in downstream_raw
            if item.get("table_name")
        ]

        return {"upstream": upstream, "downstream": downstream}

    except Exception as e:
        logger.warning("Failed to load table dependencies: %s", e)
        # Fallback to empty result to keep UI functional
        return {"upstream": [], "downstream": []}
