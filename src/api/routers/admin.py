"""Administrative and dashboard endpoints."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from ..config import config

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/v1", tags=["admin"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def get_app_state() -> Any:
    """Get application state from FastAPI app.

    This is a placeholder that will be replaced with actual state injection.
    The state will be passed via dependency injection in main.py.
    """
    # This will be replaced with proper dependency injection
    from ..main_local import state

    return state


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """List available Ollama models.

    Returns:
        Dictionary containing available models from Ollama.

    Raises:
        HTTPException: If Ollama is not available.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama not available: {e}")


@router.get("/stats")
async def get_dashboard_stats() -> Dict[str, Any]:
    """Get dashboard statistics.

    Provides high-level metrics for the dashboard including node counts,
    processed files, and trends.

    Returns:
        Dictionary with dashboard statistics.

    Raises:
        HTTPException: If graph is not initialized.

    Note:
        Some metrics (filesProcessed, activeQueries) are placeholders
        pending implementation of tracking.
    """
    state = get_app_state()

    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    stats = state.graph.get_stats()

    return {
        "totalNodes": stats.get("nodes", 0),
        "filesProcessed": 0,  # TODO: Track files processed
        "databaseTables": stats.get("Table", 0),
        "activeQueries": 0,  # TODO: Track active queries
        "trends": {
            "nodes": {"value": 12, "isPositive": True},
            "files": {"value": 8, "isPositive": True},
        },
    }


@router.get("/activity/recent")
async def get_recent_activity() -> List[Dict[str, str]]:
    """Get recent activity items.

    Returns:
        List of recent activity events.

    Note:
        Currently returns placeholder data. Full activity tracking
        to be implemented.
    """
    # TODO: Implement activity tracking
    return [
        {
            "id": "1",
            "type": "ingestion",
            "message": "Processed SQL file successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }
    ]


@router.get("/files/recent")
async def get_recent_files() -> List[Dict[str, str]]:
    """Get recently processed files.

    Returns:
        List of recently processed files with metadata.

    Note:
        Currently returns placeholder data. Full file tracking
        to be implemented.
    """
    # TODO: Implement file tracking
    return [
        {
            "id": "1",
            "name": "sample_schema.sql",
            "type": "file",
            "status": "processed",
            "updatedAt": datetime.utcnow().isoformat(),
        }
    ]


@router.get("/files")
async def get_files() -> List[Dict[str, Any]]:
    """Get all files.

    Returns:
        List of all files in storage.

    Note:
        Currently returns empty list. File listing from storage
        to be implemented.
    """
    # TODO: Implement file listing from storage
    return []


@router.get("/files/stats")
async def get_file_stats() -> Dict[str, int]:
    """Get file statistics.

    Returns:
        Dictionary with file counts by status.

    Note:
        Currently returns placeholder data. File stats tracking
        to be implemented.
    """
    # TODO: Implement file stats tracking
    return {"total": 0, "processed": 0, "pending": 0, "errors": 0}


@router.get("/files/search")
async def search_files(
    q: str = Query(..., description="Search query")
) -> List[Dict[str, Any]]:
    """Search files by query.

    Args:
        q: Search query string.

    Returns:
        List of files matching the search query.

    Note:
        Currently returns empty list. File search to be implemented.
    """
    # TODO: Implement file search
    return []


@router.get("/endpoints")
async def list_endpoints(
    tag: str = Query(None, description="Filter endpoints by tag"),
    include_params: bool = Query(False, description="Include parameter details"),
) -> Dict[str, Any]:
    """List all available API endpoints.

    Introspects FastAPI app.routes to discover all registered endpoints.
    Powers the frontend Settings page "Ping All" functionality.

    Args:
        tag: Optional tag to filter endpoints.
        include_params: If true, include parameter details for each endpoint.

    Returns:
        Dictionary with endpoints grouped by tag.
    """
    from ..main_local import app

    endpoints = []
    excluded_paths = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}

    for route in app.routes:
        # Skip internal routes
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue

        path = route.path
        if path in excluded_paths:
            continue

        # Get route metadata
        methods = list(route.methods - {"HEAD", "OPTIONS"}) if route.methods else []
        tags = getattr(route, "tags", []) or ["default"]
        description = getattr(route, "description", "") or ""
        name = getattr(route, "name", "") or ""

        # Filter by tag if specified
        if tag and tag not in tags:
            continue

        for method in methods:
            endpoint_info = {
                "method": method,
                "path": path,
                "name": name,
                "description": description[:200] if description else "",
                "tags": tags,
            }

            # Include parameter details if requested
            if include_params and hasattr(route, "dependant"):
                params = []
                dependant = route.dependant
                if hasattr(dependant, "query_params"):
                    for param in dependant.query_params:
                        params.append({
                            "name": param.name,
                            "type": str(param.type_annotation) if param.type_annotation else "string",
                            "required": param.required,
                            "in": "query",
                        })
                if hasattr(dependant, "path_params"):
                    for param in dependant.path_params:
                        params.append({
                            "name": param.name,
                            "type": str(param.type_annotation) if param.type_annotation else "string",
                            "required": True,
                            "in": "path",
                        })
                endpoint_info["parameters"] = params

            endpoints.append(endpoint_info)

    # Group by tag
    grouped = {}
    for endpoint in endpoints:
        for endpoint_tag in endpoint["tags"]:
            if endpoint_tag not in grouped:
                grouped[endpoint_tag] = []
            grouped[endpoint_tag].append(endpoint)

    return {
        "total": len(endpoints),
        "endpoints": endpoints,
        "by_tag": grouped,
    }


@admin_router.post("/restart")
async def restart_container() -> Dict[str, str]:
    """Trigger graceful container restart.

    Returns response immediately, then exits with code 0 to trigger
    Docker restart policy. The container will be restarted automatically
    by Docker.

    Returns:
        Dictionary with restart status message.

    Note:
        This endpoint sends the response before initiating shutdown,
        ensuring the frontend receives confirmation. The actual restart
        happens via Docker's restart policy.
    """
    # Schedule shutdown or reload after response is sent
    async def restart_logic():
        await asyncio.sleep(0.5)  # Give time for response to be sent
        
        # Check if running in Docker
        if os.path.exists("/.dockerenv"):
            logger.info("Docker environment detected, exiting to trigger restart policy")
            os._exit(0)
        else:
            # Local development: Trigger reload by touching main file
            try:
                # Assuming running from project root or src/api
                reload_file = Path("src/api/main_local.py")
                if not reload_file.exists():
                     # Try relative to this file
                    reload_file = Path(__file__).parent.parent / "main_local.py"
                
                if reload_file.exists():
                    logger.info(f"Local environment detected, touching {reload_file} to trigger reload")
                    reload_file.touch()
                else:
                    logger.warning("Could not find main_local.py to trigger reload, exiting process")
                    os._exit(0)
            except Exception as e:
                logger.error(f"Failed to trigger reload: {e}")
                os._exit(1)

    # Start restart task in background
    asyncio.create_task(restart_logic())

    return {"status": "restarting"}


# WebSocket Connection Manager
class ConnectionManager:
    """Manages WebSocket connections for dashboard updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and track new WebSocket connection.

        Args:
            websocket: WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection from tracking.

        Args:
            websocket: WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients.

        Args:
            message: Dictionary to send as JSON to all clients.
        """
        message_json = json.dumps(message)
        # Send to all connections, removing failed ones
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.append(connection)

        # Clean up failed connections
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates.

    Accepts WebSocket connection, sends periodic stats updates,
    and broadcasts system events to connected clients.

    Args:
        websocket: WebSocket connection from client.

    Note:
        Sends stats_update messages every 5 seconds with current
        dashboard statistics. Connection stays open until client
        disconnects or error occurs.
    """
    await manager.connect(websocket)

    try:
        # Send connection acknowledgment
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_ack",
                    "data": {"message": "Connected to dashboard"},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Send stats update every 5 seconds
                await asyncio.sleep(5)

                # Get current stats
                state = get_app_state()
                if state.graph:
                    stats = state.graph.get_stats()
                    dashboard_stats = {
                        "totalNodes": stats.get("nodes", 0),
                        "filesProcessed": 0,
                        "databaseTables": stats.get("Table", 0),
                        "activeQueries": 0,
                        "trends": {
                            "nodes": {"value": 12, "isPositive": True},
                            "files": {"value": 8, "isPositive": True},
                        },
                    }

                    # Broadcast stats update
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "stats_update",
                                "data": dashboard_stats,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )
                    )
            except WebSocketDisconnect:
                break
            except Exception as e:
                # Log error but continue connection
                print(f"[!] WebSocket error: {e}")
                break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
