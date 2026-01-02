"""
GitHub integration router for OAuth and repository ingestion.

Provides endpoints for:
- OAuth authentication with GitHub
- Repository browsing
- File ingestion with progress tracking
"""

import base64
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from src.storage.metadata_store import ProjectStore, RepositoryStore
from src.services.ingestion_tracker import get_tracker, FileStatus
from ..config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["github"])

def get_supported_extensions() -> set:
    """Get supported file extensions from config."""
    return set(ext.strip() for ext in config.ALLOWED_FILE_EXTENSIONS)

# Store instances
project_store = ProjectStore()
repository_store = RepositoryStore()

# In-memory state storage for OAuth CSRF protection
# Map state -> timestamp (TTL)
oauth_states: Dict[str, float] = {}
STATE_TTL = 600  # 10 minutes


def cleanup_states():
    """Remove expired states."""
    now = time.time()
    expired = [state for state, ts in oauth_states.items() if now - ts > STATE_TTL]
    for state in expired:
        del oauth_states[state]


class GitHubAuthResponse(BaseModel):
    auth_url: str
    state: str


class GitHubCallbackRequest(BaseModel):
    code: str
    state: str


class GitHubIngestRequest(BaseModel):
    repo: str
    project_id: str
    repository_id: Optional[str] = None
    repository_name: Optional[str] = None
    items: List[Dict[str, Any]]
    branch: str = "main"


@router.get("/auth", response_model=GitHubAuthResponse)
async def github_auth():
    """Initiate GitHub OAuth flow."""
    if not config.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub Client ID not configured")

    cleanup_states()
    state = uuid.uuid4().hex
    oauth_states[state] = time.time()

    scope = "repo,read:user"
    auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={config.GITHUB_CLIENT_ID}&"
        f"redirect_uri={config.GITHUB_REDIRECT_URI}&"
        f"scope={scope}&"
        f"state={state}"
    )

    return {"auth_url": auth_url, "state": state}


@router.post("/callback")
async def github_callback(request: GitHubCallbackRequest):
    """Exchange authorization code for access token."""
    if request.state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    del oauth_states[request.state]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": request.code,
                "redirect_uri": config.GITHUB_REDIRECT_URI,
            },
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
            
        data = response.json()
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error_description"])
            
        access_token = data["access_token"]
        
        # Fetch user info
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")
            
        return {
            "access_token": access_token,
            "user": user_resp.json()
        }


async def get_github_client(request: Request):
    """Dependency to get authenticated GitHub client."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = auth_header.split(" ")[1]
    return httpx.AsyncClient(headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    })


@router.get("/user")
async def get_user(client: httpx.AsyncClient = Depends(get_github_client)):
    """Get authenticated user info."""
    resp = await client.get("https://api.github.com/user")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="GitHub API error")
    return resp.json()


@router.get("/repos")
async def list_repos(
    page: int = 1, 
    per_page: int = 30,
    client: httpx.AsyncClient = Depends(get_github_client)
):
    """List user repositories."""
    resp = await client.get(
        "https://api.github.com/user/repos",
        params={"sort": "updated", "per_page": per_page, "page": page}
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="GitHub API error")
    
    repos = resp.json()
    return {"repositories": repos, "page": page, "per_page": per_page}


@router.get("/contents")
async def get_contents(
    repo: str,
    path: str = "",
    ref: Optional[str] = None,
    client: httpx.AsyncClient = Depends(get_github_client)
):
    """Get repository contents."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    params = {}
    if ref:
        params["ref"] = ref
        
    resp = await client.get(url, params=params)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Path not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="GitHub API error")
        
    return {"contents": resp.json(), "repo": repo, "path": path}


def is_supported_file(path: str) -> bool:
    """Check if file extension is supported for ingestion."""
    ext = Path(path).suffix.lower()
    return ext in get_supported_extensions()


async def fetch_file_content(
    client: httpx.AsyncClient,
    repo: str,
    path: str,
    ref: str = "main",
) -> Optional[str]:
    """
    Fetch file content from GitHub API.

    Args:
        client: Authenticated GitHub client
        repo: Repository full name (owner/repo)
        path: File path in repository
        ref: Git reference (branch/tag/commit)

    Returns:
        Decoded file content as string, or None if failed
    """
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    params = {"ref": ref}

    try:
        resp = await client.get(url, params=params)

        if resp.status_code == 404:
            logger.warning(f"File not found: {repo}/{path}")
            return None

        if resp.status_code == 403:
            # Check for rate limiting
            remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
            reset_time = resp.headers.get("X-RateLimit-Reset", "unknown")
            logger.error(f"GitHub rate limit: remaining={remaining}, resets={reset_time}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "github_rate_limited",
                    "remaining": remaining,
                    "reset_at": reset_time,
                }
            )

        if resp.status_code != 200:
            logger.error(f"GitHub API error {resp.status_code}: {resp.text}")
            return None

        data = resp.json()

        # Handle file content
        if data.get("type") != "file":
            logger.warning(f"Not a file: {repo}/{path}")
            return None

        # Decode base64 content
        content_b64 = data.get("content", "")
        if not content_b64:
            # Large files need blob API
            if data.get("size", 0) > 1024 * 1024:
                return await fetch_blob_content(client, repo, data.get("sha"))
            return None

        # Remove newlines from base64 and decode
        content_b64 = content_b64.replace("\n", "")
        content = base64.b64decode(content_b64).decode("utf-8")
        return content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch {repo}/{path}: {e}")
        return None


async def fetch_blob_content(
    client: httpx.AsyncClient,
    repo: str,
    sha: str,
) -> Optional[str]:
    """
    Fetch large file content using Git Blob API.

    Args:
        client: Authenticated GitHub client
        repo: Repository full name
        sha: Blob SHA

    Returns:
        Decoded file content as string, or None if failed
    """
    url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        content_b64 = data.get("content", "").replace("\n", "")
        return base64.b64decode(content_b64).decode("utf-8")

    except Exception as e:
        logger.error(f"Failed to fetch blob {sha}: {e}")
        return None


async def fetch_directory_files(
    client: httpx.AsyncClient,
    repo: str,
    path: str,
    ref: str = "main",
) -> List[str]:
    """
    Recursively fetch all file paths in a directory.

    Args:
        client: Authenticated GitHub client
        repo: Repository full name
        path: Directory path
        ref: Git reference

    Returns:
        List of file paths
    """
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    params = {"ref": ref}

    try:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []

        items = resp.json()
        if not isinstance(items, list):
            return []

        file_paths = []
        for item in items:
            if item.get("type") == "file":
                file_paths.append(item.get("path"))
            elif item.get("type") == "dir":
                # Recursively fetch subdirectory
                sub_files = await fetch_directory_files(
                    client, repo, item.get("path"), ref
                )
                file_paths.extend(sub_files)

        return file_paths

    except Exception as e:
        logger.error(f"Failed to fetch directory {repo}/{path}: {e}")
        return []


@router.post("/ingest")
async def ingest_files(
    request: GitHubIngestRequest,
    client: httpx.AsyncClient = Depends(get_github_client)
):
    """
    Ingest selected files from GitHub repository.

    Downloads files from GitHub, parses them for lineage extraction,
    and creates nodes in Neo4j with project/repository tagging.

    Broadcasts real-time progress updates via WebSocket.
    """
    # Validate project
    if not project_store.exists(request.project_id):
        raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

    # Get or create repository
    if request.repository_id:
        repo = repository_store.get(request.repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
    else:
        if not request.repository_name:
            raise HTTPException(status_code=400, detail="repository_name required")

        repo = await repository_store.create(
            project_id=request.project_id,
            name=request.repository_name,
            source="github",
            source_ref=request.repo
        )
        request.repository_id = repo["id"]

    # Collect all file paths to process
    file_paths = []
    for item in request.items:
        path = item.get("path")
        item_type = item.get("type", "file")

        if not path:
            continue

        if item_type == "dir":
            # Recursively get all files in directory
            dir_files = await fetch_directory_files(
                client, request.repo, path, request.branch
            )
            file_paths.extend(dir_files)
        else:
            file_paths.append(path)

    # Filter to supported file types
    supported_files = [p for p in file_paths if is_supported_file(p)]
    skipped_files = [p for p in file_paths if not is_supported_file(p)]

    if not supported_files:
        return {
            "success": True,
            "project_id": request.project_id,
            "repository_id": request.repository_id,
            "ingestion_id": None,
            "files_processed": 0,
            "files_skipped": len(skipped_files),
            "total_nodes_created": 0,
            "message": "No supported files found to ingest",
            "results": [{"path": p, "status": "skipped", "reason": "unsupported_type"} for p in skipped_files],
        }

    # Start ingestion session with progress tracking
    tracker = get_tracker()
    session = await tracker.start_session(
        source="github",
        project_id=request.project_id,
        repository_id=request.repository_id,
        file_paths=supported_files,
    )

    # Get app state for parser and extractor
    from ..main_local import state

    results = []
    total_nodes_created = 0

    # Process each file
    for file_path in supported_files:
        file_result = {
            "path": file_path,
            "status": "pending",
            "nodes_created": 0,
            "error": None,
        }

        try:
            # Update status: downloading
            await tracker.update_file_status(
                session.ingestion_id, file_path, FileStatus.DOWNLOADING
            )

            # Fetch file content from GitHub
            content = await fetch_file_content(
                client, request.repo, file_path, request.branch
            )

            if content is None:
                file_result["status"] = "error"
                file_result["error"] = "Failed to download file"
                await tracker.file_error(
                    session.ingestion_id, file_path, "Failed to download file"
                )
                results.append(file_result)
                continue

            # Update status: parsing
            await tracker.update_file_status(
                session.ingestion_id, file_path, FileStatus.PARSING
            )

            # Parse file for lineage extraction
            nodes_created = 0

            if state.parser and state.extractor:
                try:
                    ext = Path(file_path).suffix.lower()

                    if ext in {".sql", ".ddl"}:
                        # Update status: extracting
                        await tracker.update_file_status(
                            session.ingestion_id, file_path, FileStatus.EXTRACTING
                        )

                        parse_result = state.parser.parse(content)

                        if parse_result.get("entities"):
                            # Tag entities with project/repository metadata
                            for entity in parse_result.get("entities", []):
                                entity["project_id"] = request.project_id
                                entity["repository_id"] = request.repository_id
                                entity["source_file"] = file_path
                                entity["source"] = "github"
                                entity["source_repo"] = request.repo

                            # Add to graph
                            state.extractor.add_entities(parse_result["entities"])
                            nodes_created = len(parse_result.get("entities", []))

                except Exception as e:
                    logger.warning(f"Failed to parse {file_path}: {e}")
                    file_result["error"] = f"Parse error: {str(e)}"

            file_result["status"] = "processed"
            file_result["nodes_created"] = nodes_created
            total_nodes_created += nodes_created

            # Mark file complete
            await tracker.file_complete(
                session.ingestion_id, file_path, nodes_created
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            file_result["status"] = "error"
            file_result["error"] = str(e)
            await tracker.file_error(session.ingestion_id, file_path, str(e))

        results.append(file_result)

    # Add skipped files to results
    for skipped_path in skipped_files:
        results.append({
            "path": skipped_path,
            "status": "skipped",
            "nodes_created": 0,
            "error": "unsupported_file_type",
        })
        await tracker.file_skipped(session.ingestion_id, skipped_path)

    # Complete session
    completed_session = await tracker.complete_session(session.ingestion_id)

    # Update repository counts
    try:
        await repository_store.update_counts(
            repo_id=request.repository_id,
            file_count=(repo.get("file_count", 0) or 0) + len(supported_files),
            node_count=(repo.get("node_count", 0) or 0) + total_nodes_created,
        )
        await repository_store.update_last_synced(request.repository_id)
    except Exception as e:
        logger.warning(f"Failed to update repository counts: {e}")

    return {
        "success": True,
        "project_id": request.project_id,
        "repository_id": request.repository_id,
        "ingestion_id": session.ingestion_id,
        "files_processed": len(supported_files),
        "files_skipped": len(skipped_files),
        "files_failed": completed_session.files_failed if completed_session else 0,
        "total_nodes_created": total_nodes_created,
        "results": results,
    }


@router.get("/ingest/status/{ingestion_id}")
async def get_ingestion_status(ingestion_id: str):
    """Get status of an ingestion session."""
    tracker = get_tracker()
    session = tracker.get_session(ingestion_id)

    if not session:
        raise HTTPException(status_code=404, detail="Ingestion session not found")

    return session.to_dict()


@router.get("/ingest/history")
async def get_ingestion_history(
    project_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get ingestion history, optionally filtered by project."""
    tracker = get_tracker()
    return {"ingestions": tracker.get_history(project_id=project_id, limit=limit)}
