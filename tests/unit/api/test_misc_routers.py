import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

# Mock src.api.main_local BEFORE importing routers that depend on it
mock_main_local = MagicMock()
mock_real_app = MagicMock() # The app expected by list_endpoints
mock_main_local.app = mock_real_app
sys.modules["src.api.main_local"] = mock_main_local

from src.api.routers import database, admin

# Create isolated app for testing
app = FastAPI()
app.include_router(database.router)
app.include_router(admin.router)

client = TestClient(app)

@pytest.fixture
def mock_graph_state():
    with patch("src.api.routers.database.get_app_state") as mock_state:
        state_obj = MagicMock()
        graph_obj = MagicMock()
        state_obj.graph = graph_obj
        mock_state.return_value = state_obj
        
        # Mock session context manager
        session_mock = MagicMock()
        graph_obj.driver.session.return_value.__enter__.return_value = session_mock
        graph_obj.database = "neo4j"
        
        yield state_obj, session_mock

@pytest.mark.asyncio
async def test_get_schemas_success(mock_graph_state):
    _, session_mock = mock_graph_state
    
    # Mock Neo4j result
    mock_record = {
        "schema_name": "public",
        "description": "Public Schema",
        "table_count": 5,
        "tables": [{"name": "users", "type": "table"}]
    }
    session_mock.run.return_value = [mock_record]
    
    response = client.get("/api/v1/database/schemas")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["schemas"][0]["name"] == "public"
    assert data["schemas"][0]["table_count"] == 5

@pytest.mark.asyncio
async def test_get_schemas_filter(mock_graph_state):
    _, session_mock = mock_graph_state
    session_mock.run.return_value = []
    
    response = client.get("/api/v1/database/schemas?schema=private")
    
    assert response.status_code == 200
    # verify query param was used - checking args passed to run
    call_args = session_mock.run.call_args
    assert call_args is not None
    assert call_args[0][1]["schema_name"] == "private"

@pytest.mark.asyncio
async def test_get_schemas_graph_not_init(mock_graph_state):
    state_obj, _ = mock_graph_state
    state_obj.graph = None # Simulate not initialized
    
    response = client.get("/api/v1/database/schemas")
    
    assert response.status_code == 503
    assert "Graph database not initialized" in response.json()["detail"]

@pytest.mark.asyncio
async def test_list_endpoints_discovery():
    # Setup mock routes on the mocked main_local.app
    mock_route_1 = MagicMock()
    mock_route_1.path = "/api/v1/test"
    mock_route_1.methods = {"GET"}
    mock_route_1.tags = ["test"]
    mock_route_1.description = "Test Endpoint"
    mock_route_1.name = "test_endpoint"
    
    mock_real_app.routes = [mock_route_1]
    
    response = client.get("/api/v1/endpoints")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["endpoints"][0]["path"] == "/api/v1/test"
    assert "test" in data["by_tag"]

@pytest.mark.asyncio
async def test_list_endpoints_filter():
    mock_route_1 = MagicMock()
    mock_route_1.path = "/api/v1/a"
    mock_route_1.methods = {"GET"}
    mock_route_1.tags = ["tag_a"]
    
    mock_route_2 = MagicMock()
    mock_route_2.path = "/api/v1/b"
    mock_route_2.methods = {"GET"}
    mock_route_2.tags = ["tag_b"]

    mock_real_app.routes = [mock_route_1, mock_route_2]
    
    response = client.get("/api/v1/endpoints?tag=tag_a")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["endpoints"]) == 1
    assert data["endpoints"][0]["path"] == "/api/v1/a"
