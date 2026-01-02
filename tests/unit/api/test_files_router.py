import pytest
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from src.api.routers import files

# Create isolated app for testing
app = FastAPI()
app.include_router(files.router)

client = TestClient(app)

@pytest.fixture
def mock_stores():
    with patch("src.api.routers.files.project_store") as mock_proj, \
         patch("src.api.routers.files.repository_store") as mock_repo, \
         patch("src.api.routers.files.config") as mock_config, \
         patch("src.api.routers.files.get_app_state") as mock_state, \
         patch("src.api.routers.files.open", mock_open()) as mock_file_open, \
         patch("src.api.routers.files.Path.mkdir") as mock_mkdir:
        
        # Default Config
        mock_config.UPLOAD_BASE_DIR = "/tmp/uploads"
        mock_config.UPLOAD_MAX_FILE_SIZE_MB = 10
        files.MAX_FILE_SIZE = 10 * 1024 * 1024  # Update module constant
        
        # Default Store Behavior
        mock_proj.exists.return_value = True
        mock_repo.get.return_value = {"id": "repo_123", "project_id": "proj_123", "file_count": 0}
        mock_repo.create = AsyncMock(return_value={"id": "new_repo_id", "project_id": "proj_123"})
        mock_repo.update_counts = AsyncMock()
        
        # Mock State (Parser/Extractor) - Default to None/Inactive to simplify basic upload test
        mock_state_obj = MagicMock()
        mock_state_obj.parser = None
        mock_state_obj.extractor = None
        mock_state.return_value = mock_state_obj

        yield mock_proj, mock_repo, mock_config, mock_state

@pytest.mark.asyncio
async def test_upload_existing_repo_success(mock_stores):
    mock_proj, mock_repo, _, _ = mock_stores
    
    files_to_upload = [
        ('files', ('test.sql', b'SELECT * FROM table', 'application/sql'))
    ]
    data = {
        "project_id": "proj_123",
        "repository_id": "repo_123"
    }
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 200
    res = response.json()
    assert res["project_id"] == "proj_123"
    assert res["repository_id"] == "repo_123"
    assert res["files_processed"] == 1
    assert res["files_failed"] == 0
    assert res["results"][0]["status"] == "processed"
    assert res["results"][0]["filename"] == "test.sql"

@pytest.mark.asyncio
async def test_upload_new_repo_success(mock_stores):
    mock_proj, mock_repo, _, _ = mock_stores
    
    files_to_upload = [('files', ('test.json', b'{}', 'application/json'))]
    data = {
        "project_id": "proj_123",
        "repository_name": "New Repo"
    }
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 200
    res = response.json()
    assert res["repository_id"] == "new_repo_id"
    mock_repo.create.assert_called_once()
    assert mock_repo.create.call_args[1]["name"] == "New Repo"

@pytest.mark.asyncio
async def test_project_not_found(mock_stores):
    mock_proj, _, _, _ = mock_stores
    mock_proj.exists.return_value = False
    
    files_to_upload = [('files', ('test.sql', b'', 'application/sql'))]
    data = {"project_id": "missing_proj", "repository_name": "R"}
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_repo_not_found(mock_stores):
    mock_proj, mock_repo, _, _ = mock_stores
    mock_repo.get.return_value = None
    
    files_to_upload = [('files', ('test.sql', b'', 'application/sql'))]
    data = {"project_id": "proj_123", "repository_id": "missing_repo"}
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_repo_project_mismatch(mock_stores):
    mock_proj, mock_repo, _, _ = mock_stores
    # Repo belongs to other_proj
    mock_repo.get.return_value = {"id": "repo_123", "project_id": "other_proj"}
    
    files_to_upload = [('files', ('test.sql', b'', 'application/sql'))]
    data = {"project_id": "proj_123", "repository_id": "repo_123"}
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 400
    assert "does not belong to project" in response.json()["detail"]

@pytest.mark.asyncio
async def test_missing_repo_name(mock_stores):
    # Missing repo_id AND repo_name
    files_to_upload = [('files', ('test.sql', b'', 'application/sql'))]
    data = {"project_id": "proj_123"}
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 400
    assert "repository_name is required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_invalid_file_extension(mock_stores):
    files_to_upload = [('files', ('test.exe', b'exec', 'application/octet-stream'))]
    data = {"project_id": "proj_123", "repository_name": "R"}
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 200 # Endpoint returns 200 with error details in body
    res = response.json()
    assert res["files_failed"] == 1
    assert res["results"][0]["status"] == "error"
    assert "Unsupported file type" in res["results"][0]["error"]

@pytest.mark.asyncio
async def test_file_too_large(mock_stores):
    mock_proj, mock_repo, mock_config, _ = mock_stores
    
    # Simulate max size 1 byte
    mock_config.UPLOAD_MAX_FILE_SIZE_MB = 0.000001
    files.MAX_FILE_SIZE = 1 # Force module constant update
    
    files_to_upload = [('files', ('large.sql', b'too large', 'application/sql'))]
    data = {"project_id": "proj_123", "repository_name": "R"}
    
    response = client.post("/api/v1/files/upload", files=files_to_upload, data=data)
    
    assert response.status_code == 200
    res = response.json()
    assert res["files_failed"] == 1
    assert "File too large" in res["results"][0]["error"]
