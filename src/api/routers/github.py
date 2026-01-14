"""
GitHub integration router for OAuth and repository ingestion.

Provides endpoints for:
- OAuth authentication with GitHub
- Repository browsing
- File ingestion with progress tracking
"""

import base64
import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from src.storage import ArtifactManager
from src.storage.graph_snapshot import GraphSnapshotManager
from src.storage.metadata_store import ProjectStore, RepositoryStore
from src.services.ingestion_tracker import get_tracker, FileStatus
from src.services.ingestion_pipeline import index_file_content, purge_before_ingest
from src.utils.file_metadata import infer_file_type, sanitize_relative_path
from src.config.sql_dialects import format_dialect_error, validate_dialect
from ..config import config
from ..middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/github",
    tags=["github"],
    dependencies=[Depends(get_current_user)],
)


def get_supported_extensions() -> set:
    """Get supported file extensions from config."""
    return set(ext.strip() for ext in config.ALLOWED_FILE_EXTENSIONS)


# Store instances
project_store = ProjectStore()
repository_store = RepositoryStore()
artifact_manager = ArtifactManager(base_path="data")

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
    dialect: str = "auto"
    verbose: bool = False


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
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")

        return {"access_token": access_token, "user": user_resp.json()}


async def get_github_client(request: Request):
    """Dependency to get authenticated GitHub client."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    )


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
    client: httpx.AsyncClient = Depends(get_github_client),
):
    """List user repositories."""
    resp = await client.get(
        "https://api.github.com/user/repos",
        params={"sort": "updated", "per_page": per_page, "page": page},
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
    client: httpx.AsyncClient = Depends(get_github_client),
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
            logger.error(
                f"GitHub rate limit: remaining={remaining}, resets={reset_time}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "github_rate_limited",
                    "remaining": remaining,
                    "reset_at": reset_time,
                },
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
    request: GitHubIngestRequest, client: httpx.AsyncClient = Depends(get_github_client)
):
    """
    Ingest selected files from GitHub repository.

    Downloads files from GitHub, parses them for lineage extraction,
    and creates nodes in Neo4j with project/repository tagging.

    Broadcasts real-time progress updates via WebSocket.
    Saves files to hierarchical run directory with content deduplication.
    """
    # Validate project
    project = project_store.get(request.project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project {request.project_id} not found"
        )

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
            source_ref=request.repo,
        )
        request.repository_id = repo["id"]

    dialect_value = (request.dialect or "auto").strip()
    if not validate_dialect(dialect_value):
        raise HTTPException(status_code=400, detail=format_dialect_error(dialect_value))

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
    normalized_paths = {path: sanitize_relative_path(path) for path in supported_files}

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
            "results": [
                {"path": p, "status": "skipped", "reason": "unsupported_type"}
                for p in skipped_files
            ],
        }

    # Create ingestion run for this GitHub sync
    run_context = await artifact_manager.create_run(
        project_id=request.project_id,
        project_name=project["name"],
        action=f"github_sync_{request.repo.replace('/', '_')}",
    )

    # Get raw_source directory for this run
    raw_source_dir = run_context.get_artifact_dir("raw_source")
    raw_source_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = run_context.get_artifact_dir("chunks")
    chunks_dir.mkdir(parents=True, exist_ok=True)
    validations_dir = run_context.get_artifact_dir("validations")
    validations_dir.mkdir(parents=True, exist_ok=True)
    embeddings_dir = run_context.get_artifact_dir("embeddings")
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    # Start ingestion session with progress tracking
    tracker = get_tracker()
    session = await tracker.start_session(
        source="github",
        project_id=request.project_id,
        repository_id=request.repository_id,
        file_paths=list(normalized_paths.values()),
        log_dir=run_context.run_dir,
        verbose=request.verbose,
        run_id=run_context.run_id,
        project_status=project.get("status", "active"),
        source_repo=request.repo,
    )
    await tracker.log_debug(
        session.ingestion_id,
        "run_context_created",
        {
            "run_id": run_context.run_id,
            "run_dir": str(run_context.run_dir),
        },
    )

    # Get app state for parser and extractor
    from ..main_local import state

    snapshot_info = None
    if state.graph:
        try:
            snapshot_manager = GraphSnapshotManager(
                state.graph,
                storage_root=config.STORAGE_PATH,
            )
            snapshot_info = snapshot_manager.create_snapshot(
                project_name=project["name"],
                ingestion_id=session.ingestion_id,
                project_id=request.project_id,
                run_id=run_context.run_id,
                run_dir=run_context.run_dir,
                file_paths=list(normalized_paths.values()),
            )
            await tracker.log_stage(
                session.ingestion_id,
                stage="graph_snapshot",
                status="completed",
                summary={
                    "snapshot_path": snapshot_info.path,
                    "node_count": snapshot_info.node_count,
                    "edge_count": snapshot_info.edge_count,
                    "project_name": snapshot_info.project_name,
                    "file_count": len(normalized_paths),
                },
            )
        except Exception as e:
            await tracker.log_stage(
                session.ingestion_id,
                stage="graph_snapshot",
                status="failed",
                error=str(e),
                summary={
                    "project_name": project["name"],
                },
            )

    results = []
    total_nodes_created = 0
    files_skipped_duplicate = 0

    # Process each file
    for file_path in supported_files:
        relative_path = normalized_paths.get(file_path, file_path)
        file_result = {
            "path": file_path,
            "relative_path": relative_path,
            "file_type": infer_file_type(relative_path),
            "status": "pending",
            "nodes_created": 0,
            "error": None,
        }
        file_id = None

        try:
            # Update status: downloading
            await tracker.update_file_status(
                session.ingestion_id, relative_path, FileStatus.DOWNLOADING
            )

            # Fetch file content from GitHub
            content = await fetch_file_content(
                client, request.repo, file_path, request.branch
            )

            if content is None:
                file_result["status"] = "error"
                file_result["error"] = "Failed to download file"
                await tracker.file_error(
                    session.ingestion_id, relative_path, "Failed to download file"
                )
                results.append(file_result)
                continue

            # Save file to run directory
            filename = Path(relative_path).name
            local_file_path = raw_source_dir / relative_path

            # Create subdirectory structure if needed
            local_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            with open(local_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            await tracker.log_debug(
                session.ingestion_id,
                "file_saved",
                {
                    "path": str(local_file_path),
                    "file": relative_path,
                },
            )

            # Register file with content hashing and deduplication
            registration = await artifact_manager.register_file(
                project_id=request.project_id,
                run_id=run_context.run_id,
                filename=filename,
                file_path=local_file_path,
                relative_path=relative_path,
                file_type=infer_file_type(relative_path),
                source="github",
                repository_id=request.repository_id,
                status="pending",
            )
            file_id = registration.get("file_id")

            file_result["file_hash"] = registration["file_hash"]
            file_result["file_status"] = registration["status"]
            file_result["saved_path"] = str(local_file_path)
            await tracker.log_debug(
                session.ingestion_id,
                "file_registered",
                {
                    "file": relative_path,
                    "status": registration.get("status"),
                    "file_hash": registration.get("file_hash"),
                },
            )

            # Check if this is a duplicate (same content)
            if registration["skip_processing"]:
                logger.info(f"Skipping processing for duplicate file: {relative_path}")
                file_result["status"] = "skipped_duplicate"
                file_result["message"] = registration["message"]
                files_skipped_duplicate += 1
                await tracker.file_skipped(session.ingestion_id, relative_path)
                await tracker.log_stage(
                    session.ingestion_id,
                    stage="deduplication",
                    status="skipped",
                    file_path=relative_path,
                    summary={"reason": "duplicate"},
                )
                await tracker.log_debug(
                    session.ingestion_id,
                    "file_skipped_duplicate",
                    {
                        "file": relative_path,
                        "message": registration.get("message"),
                    },
                )
                results.append(file_result)
                continue

            # Update status: parsing
            await tracker.update_file_status(
                session.ingestion_id, relative_path, FileStatus.PARSING
            )

            await purge_before_ingest(
                file_path=relative_path,
                state=state,
                tracker=tracker,
                ingestion_id=session.ingestion_id,
                project_id=request.project_id,
                repository_id=request.repository_id,
            )

            # Parse file for lineage extraction
            nodes_created = 0

            ext = Path(relative_path).suffix.lower()
            plugin = None

            if state.parser and state.extractor:
                try:
                    plugin = (
                        state.plugin_registry.get_for_extension(ext)
                        if state.plugin_registry
                        else None
                    )

                    if ext in {".sql", ".ddl"}:
                        # Log parsing stage started
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="parsing",
                            status="started",
                            file_path=relative_path,
                        )
                        await tracker.log_debug(
                            session.ingestion_id,
                            "sql_ingest_start",
                            {
                                "file": relative_path,
                                "dialect": dialect_value,
                            },
                        )
                        # Update status: extracting
                        await tracker.update_file_status(
                            session.ingestion_id, relative_path, FileStatus.EXTRACTING
                        )

                        # Log lineage stage started
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="lineage",
                            status="started",
                            file_path=relative_path,
                        )

                        if plugin:
                            result = plugin.parse(
                                content,
                                {"dialect": dialect_value, "file_path": relative_path},
                            )
                            nodes_created = state.extractor.ingest_lineage_result(
                                result,
                                project_id=request.project_id,
                                repository_id=request.repository_id,
                                source_file=relative_path,
                                source="github",
                                source_repo=request.repo,
                            )
                        else:
                            nodes_created = (
                                state.extractor.ingest_sql_lineage(
                                    sql_content=content,
                                    dialect=dialect_value,
                                    source_file=relative_path,
                                    project_id=request.project_id,
                                    repository_id=request.repository_id,
                                    source="github",
                                    source_repo=request.repo,
                                )
                                or 0
                            )

                        # Log parsing completed
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="parsing",
                            status="completed",
                            file_path=relative_path,
                            summary={"nodes_created": nodes_created},
                        )

                        # Log lineage completed
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="lineage",
                            status="completed",
                            file_path=relative_path,
                            summary={"nodes_created": nodes_created},
                        )

                        await tracker.log_debug(
                            session.ingestion_id,
                            "sql_ingest_complete",
                            {
                                "file": relative_path,
                                "nodes_created": nodes_created,
                            },
                        )
                        state.extractor.flush_batch()
                    elif ext == ".py":
                        await tracker.update_file_status(
                            session.ingestion_id, relative_path, FileStatus.EXTRACTING
                        )
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="parsing",
                            status="started",
                            file_path=relative_path,
                        )
                        if plugin:
                            result = plugin.parse(
                                content,
                                {"file_path": relative_path},
                            )
                            nodes_created = state.extractor.ingest_lineage_result(
                                result,
                                project_id=request.project_id,
                                repository_id=request.repository_id,
                                source_file=relative_path,
                                source="github",
                                source_repo=request.repo,
                            )
                        else:
                            state.extractor.ingest_python(
                                content=content,
                                source_file=relative_path,
                                project_id=project_id,
                            )
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="parsing",
                            status="completed",
                            file_path=relative_path,
                            summary={"nodes_created": nodes_created},
                        )
                        state.extractor.flush_batch()
                    elif plugin:
                        result = plugin.parse(
                            content,
                            {"file_path": relative_path},
                        )
                        nodes_created = state.extractor.ingest_lineage_result(
                            result,
                            project_id=request.project_id,
                            repository_id=request.repository_id,
                            source_file=relative_path,
                            source="github",
                            source_repo=request.repo,
                        )
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="parsing",
                            status="completed",
                            file_path=relative_path,
                            summary={"nodes_created": nodes_created},
                        )
                        state.extractor.flush_batch()
                    else:
                        logger.warning(
                            "No lineage plugin registered for extension: %s", ext
                        )

                except Exception as e:
                    logger.warning(f"Failed to parse {relative_path}: {e}")

                    # Log stage failure
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="parsing",
                        status="failed",
                        file_path=relative_path,
                        error=str(e),
                    )

                    file_result["status"] = "error"
                    file_result["error"] = f"Parse error: {str(e)}"
                    if file_id:
                        await artifact_manager.update_file_status(file_id, "error")
                    await tracker.file_error(
                        session.ingestion_id,
                        relative_path,
                        file_result["error"],
                    )
                    results.append(file_result)
                    continue

            index_result = await index_file_content(
                content=content,
                file_path=relative_path,
                state=state,
                tracker=tracker,
                ingestion_id=session.ingestion_id,
                project_id=request.project_id,
                repository_id=request.repository_id,
                source="github",
                dialect=dialect_value,
                chunk_output_dir=str(chunks_dir),
                embeddings_output_dir=str(embeddings_dir),
            )
            file_result["indexing"] = {
                "mode": index_result.get("mode"),
                "chunks": index_result.get("chunks"),
                "indexed": index_result.get("indexed"),
            }
            if index_result.get("error"):
                if index_result.get("mode") == "skipped":
                    file_result["status"] = "skipped"
                    file_result["error"] = index_result["error"]
                    if file_id:
                        await artifact_manager.update_file_status(file_id, "skipped")
                    await tracker.file_skipped(
                        session.ingestion_id,
                        relative_path,
                        reason=index_result["error"],
                    )
                    results.append(file_result)
                    continue

                file_result["status"] = "error"
                file_result["error"] = f"Indexing failed: {index_result['error']}"
                if file_id:
                    await artifact_manager.update_file_status(file_id, "error")
                await tracker.file_error(
                    session.ingestion_id,
                    relative_path,
                    file_result["error"],
                )
                results.append(file_result)
                continue

            validation_summary = None
            if state.validation_agent:
                validation_summary = state.validation_agent.validate_content(
                    content=content,
                    plugin=plugin,
                    file_path=relative_path,
                    project_id=request.project_id,
                    dialect=dialect_value if ext in {".sql", ".ddl"} else None,
                )
                validation_payload = validation_summary.to_dict()
                validation_payload["file_path"] = relative_path
                validation_payload["project_id"] = request.project_id
                validation_payload["ingestion_id"] = session.ingestion_id
                safe_validation_name = relative_path.replace("/", "_").replace(
                    "\\", "_"
                )
                validation_filename = f"{safe_validation_name}_validation.json"
                validation_path = validations_dir / validation_filename
                try:
                    with validation_path.open("w", encoding="utf-8") as handle:
                        json.dump(
                            validation_payload, handle, indent=2, ensure_ascii=False
                        )
                except Exception as exc:
                    logger.warning(
                        "Failed to write validation artifact for %s: %s",
                        relative_path,
                        exc,
                    )
                    validation_path = None
                await tracker.log_stage(
                    session.ingestion_id,
                    stage="validation",
                    status=(
                        "completed"
                        if validation_summary.status in {"passed", "failed"}
                        else (
                            "failed"
                            if validation_summary.status == "error"
                            else validation_summary.status
                        )
                    ),
                    file_path=relative_path,
                    summary={
                        "status": validation_summary.status,
                        "missing_nodes": len(validation_summary.missing_nodes),
                        "missing_edges": len(validation_summary.missing_edges),
                        "artifact_path": (
                            str(validation_path) if validation_path else None
                        ),
                    },
                    error=validation_summary.error,
                )
                file_result["validation"] = validation_payload
                file_result["validation_artifact"] = (
                    str(validation_path) if validation_path else None
                )

            kg_summary = None
            if state.kg_agent:
                snippet = content
                if len(snippet) > 8000:
                    snippet = snippet[:8000]
                kg_summary = await state.kg_agent.enrich_file(
                    code_snippet=snippet,
                    file_path=relative_path,
                    project_id=request.project_id,
                    ingestion_id=session.ingestion_id,
                )
                await tracker.log_stage(
                    session.ingestion_id,
                    stage="kg_enrichment",
                    status="completed" if not kg_summary.error else "failed",
                    file_path=relative_path,
                    summary={
                        "model": kg_summary.model,
                        "proposed_edges": kg_summary.proposed_edges,
                        "accepted_edges": kg_summary.accepted_edges,
                        "confidence_min": kg_summary.confidence_min,
                        "confidence_avg": kg_summary.confidence_avg,
                        "confidence_max": kg_summary.confidence_max,
                    },
                    error=kg_summary.error,
                )
                file_result["kg_enrichment"] = kg_summary.to_dict()

            # Mark file as processed in artifact manager
            if file_id:
                await artifact_manager.mark_file_processed(file_id)

            file_result["status"] = "processed"
            file_result["nodes_created"] = nodes_created
            total_nodes_created += nodes_created

            # Mark file complete
            await tracker.file_complete(
                session.ingestion_id, relative_path, nodes_created
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing {relative_path}: {e}")
            file_result["status"] = "error"
            file_result["error"] = str(e)
            if file_id:
                await artifact_manager.update_file_status(file_id, "error")
            await tracker.file_error(session.ingestion_id, relative_path, str(e))

        results.append(file_result)

    # Add skipped files to results
    for skipped_path in skipped_files:
        results.append(
            {
                "path": skipped_path,
                "status": "skipped",
                "nodes_created": 0,
                "error": "unsupported_file_type",
            }
        )
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

    # Mark run as completed
    run_status = (
        "completed"
        if (completed_session.files_failed if completed_session else 0) == 0
        else "completed_with_errors"
    )
    await artifact_manager.complete_run(
        run_id=run_context.run_id,
        status=run_status,
        error_message=(
            f"{completed_session.files_failed} files failed"
            if (completed_session and completed_session.files_failed > 0)
            else None
        ),
    )

    return {
        "success": True,
        "project_id": request.project_id,
        "repository_id": request.repository_id,
        "run_id": run_context.run_id,
        "run_dir": str(run_context.run_dir),
        "snapshot": snapshot_info.__dict__ if snapshot_info else None,
        "ingestion_id": session.ingestion_id,
        "files_processed": len(supported_files),
        "files_skipped": len(skipped_files),
        "files_skipped_duplicate": files_skipped_duplicate,
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
