import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routers import github

# Create isolated app for testing
app = FastAPI()
app.include_router(github.router)

client = TestClient(app)

@pytest.fixture
def mock_config():
    with patch("src.api.routers.github.config") as mock:
        mock.GITHUB_CLIENT_ID = "test_client_id"
        mock.GITHUB_CLIENT_SECRET = "test_client_secret"
        mock.GITHUB_REDIRECT_URI = "http://localhost:3000/callback"
        yield mock

@pytest.fixture
def mock_stores():
    with patch("src.api.routers.github.project_store") as mock_proj, \
         patch("src.api.routers.github.repository_store") as mock_repo:
        
        # Setup common mock behaviors
        mock_proj.exists.return_value = True
        
        mock_repo.create = AsyncMock(return_value={"id": "new_repo_id", "file_count": 0})
        mock_repo.get.return_value = {"id": "existing_repo_id", "file_count": 5}
        mock_repo.update_counts = AsyncMock()
        
        yield mock_proj, mock_repo

@pytest.fixture
def mock_github_client_dependency():
    # Mock the dependency that returns the httpx client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    # Default successful response
    mock_valid_response = MagicMock()
    mock_valid_response.status_code = 200
    mock_valid_response.json.return_value = {}
    mock_client.get.return_value = mock_valid_response
    
    app.dependency_overrides[github.get_github_client] = lambda: mock_client
    yield mock_client
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_github_auth(mock_config):
    response = client.get("/api/v1/github/auth")
    assert response.status_code == 200
    data = response.json()
    assert "auth_url" in data
    assert "state" in data
    assert "client_id=test_client_id" in data["auth_url"]
    assert data["state"] in github.oauth_states

@pytest.mark.asyncio
async def test_github_callback_success(mock_config):
    # Setup state
    state = "test_state"
    github.oauth_states[state] = 1234567890.0
    
    mock_httpx_response = MagicMock()
    mock_httpx_response.status_code = 200
    mock_httpx_response.json.side_effect = [
        {"access_token": "test_token", "token_type": "bearer"}, # Token response
        {"login": "testuser", "id": 123} # User info response
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        
        mock_post.return_value = mock_httpx_response
        mock_get.return_value = mock_httpx_response
        
        response = client.post("/api/v1/github/callback", json={"code": "test_code", "state": state})
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "test_token"
        assert data["user"]["login"] == "testuser"

@pytest.mark.asyncio
async def test_get_user(mock_github_client_dependency):
    mock_github_client_dependency.get.return_value.json.return_value = {"login": "testuser"}
    
    response = client.get("/api/v1/github/user", headers={"Authorization": "Bearer test_token"})
    
    assert response.status_code == 200
    assert response.json()["login"] == "testuser"

@pytest.mark.asyncio
async def test_list_repos(mock_github_client_dependency):
    repos = [{"name": "repo1"}, {"name": "repo2"}]
    mock_github_client_dependency.get.return_value.json.return_value = repos
    
    response = client.get("/api/v1/github/repos", headers={"Authorization": "Bearer test_token"})
    
    assert response.status_code == 200
    assert response.json()["repositories"] == repos
    assert response.json()["page"] == 1

@pytest.mark.asyncio
async def test_get_contents(mock_github_client_dependency):
    contents = [{"name": "file1.py", "type": "file"}]
    mock_github_client_dependency.get.return_value.json.return_value = contents
    
    response = client.get("/api/v1/github/contents?repo=user/repo", headers={"Authorization": "Bearer test_token"})
    
    assert response.status_code == 200
    assert response.json()["contents"] == contents
    assert response.json()["repo"] == "user/repo"

@pytest.mark.asyncio
async def test_ingest_files_success(mock_stores, mock_github_client_dependency):
    mock_proj, mock_repo = mock_stores
    
    payload = {
        "repo": "user/repo",
        "project_id": "proj_123",
        "repository_name": "My Repo",
        "items": [{"path": "main.py", "type": "file"}]
    }
    
    response = client.post("/api/v1/github/ingest", json=payload, headers={"Authorization": "Bearer test_token"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["project_id"] == "proj_123"
    assert data["repository_id"] == "new_repo_id"
    assert data["files_processed"] == 1

@pytest.mark.asyncio
async def test_ingest_files_project_not_found(mock_stores, mock_github_client_dependency):
    mock_proj, _ = mock_stores
    mock_proj.exists.return_value = False
    
    payload = {
        "repo": "user/repo",
        "project_id": "non_existent_proj",
        "repository_name": "My Repo",
        "items": []
    }
    
    response = client.post("/api/v1/github/ingest", json=payload, headers={"Authorization": "Bearer test_token"})
    
    assert response.status_code == 404
