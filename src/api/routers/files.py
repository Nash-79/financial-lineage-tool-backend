"""
Files router for file upload and management.

Provides endpoints for uploading files with project scoping.
"""

import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.storage.metadata_store import ProjectStore, RepositoryStore
from ..config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"])

# Store instances
project_store = ProjectStore()
repository_store = RepositoryStore()

# Maximum file size (50MB by default)
MAX_FILE_SIZE = config.UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024


def get_allowed_extensions() -> set:
    """Get allowed file extensions from config."""
    return set(ext.strip() for ext in config.ALLOWED_FILE_EXTENSIONS)


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state
    return state


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace suspicious characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)

    # Remove leading dots (hidden files)
    filename = filename.lstrip('.')

    # Ensure we have a valid filename
    if not filename:
        filename = "unnamed_file"

    return filename


def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in get_allowed_extensions()


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    project_id: str = Form(..., description="Project ID (required)"),
    repository_id: Optional[str] = Form(None, description="Repository ID (optional, creates new if omitted)"),
    repository_name: Optional[str] = Form(None, description="Repository name (required if repository_id omitted)"),
) -> Dict[str, Any]:
    """
    Upload files for ingestion with project scoping.

    Files are validated, sanitized, and saved to the upload directory.
    Then they are processed for lineage extraction and tagged with
    project_id and repository_id.

    Args:
        files: List of files to upload
        project_id: Parent project ID (required)
        repository_id: Existing repository ID (optional)
        repository_name: Name for new repository (required if repository_id not provided)

    Returns:
        Dictionary with upload results for each file
    """
    # Validate project exists
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Get or create repository
    if repository_id:
        repo = repository_store.get(repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repository not found: {repository_id}")
        if repo["project_id"] != project_id:
            raise HTTPException(
                status_code=400,
                detail=f"Repository {repository_id} does not belong to project {project_id}"
            )
    else:
        # Create new repository
        if not repository_name:
            raise HTTPException(
                status_code=400,
                detail="repository_name is required when repository_id is not provided"
            )
        repo = await repository_store.create(
            project_id=project_id,
            name=repository_name,
            source="upload",
            source_ref=f"upload/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        )
        repository_id = repo["id"]
        logger.info(f"Created repository {repository_id} for upload")

    # Ensure upload directory exists
    upload_dir = Path(config.UPLOAD_BASE_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Process each file
    results = []
    total_nodes_created = 0
    files_processed = 0
    files_failed = 0

    for upload_file in files:
        file_result = {
            "filename": upload_file.filename,
            "status": "pending",
            "error": None,
            "nodes_created": 0,
            "saved_path": None,
        }

        try:
            # Validate file extension
            if not validate_file_extension(upload_file.filename):
                file_result["status"] = "error"
                file_result["error"] = f"Unsupported file type. Allowed: {', '.join(get_allowed_extensions())}"
                files_failed += 1
                results.append(file_result)
                continue

            # Read file content
            content = await upload_file.read()

            # Validate file size
            if len(content) > MAX_FILE_SIZE:
                file_result["status"] = "error"
                file_result["error"] = f"File too large. Maximum size: {config.UPLOAD_MAX_FILE_SIZE_MB}MB"
                files_failed += 1
                results.append(file_result)
                continue

            # Sanitize filename and create unique path
            safe_filename = sanitize_filename(upload_file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{safe_filename}"
            file_path = upload_dir / unique_filename

            # Save file
            with open(file_path, "wb") as f:
                f.write(content)

            file_result["saved_path"] = str(file_path)
            logger.info(f"Saved uploaded file: {file_path}")

            # Process file for lineage extraction
            state = get_app_state()
            nodes_created = 0

            if state.parser and state.extractor:
                try:
                    # Parse file
                    ext = Path(upload_file.filename).suffix.lower()
                    if ext in {".sql", ".ddl"}:
                        content_str = content.decode("utf-8")
                        parse_result = state.parser.parse(content_str)

                        if parse_result.get("entities"):
                            # Extract to graph with project/repository tagging
                            # Note: This requires updating the extractor to support tagging
                            for entity in parse_result.get("entities", []):
                                # Add project_id and repository_id to entity properties
                                entity["project_id"] = project_id
                                entity["repository_id"] = repository_id
                                entity["source_file"] = str(file_path)

                            # Add to graph
                            state.extractor.add_entities(parse_result["entities"])
                            nodes_created = len(parse_result.get("entities", []))

                except Exception as e:
                    logger.warning(f"Failed to extract lineage from {upload_file.filename}: {e}")

            file_result["status"] = "processed"
            file_result["nodes_created"] = nodes_created
            total_nodes_created += nodes_created
            files_processed += 1

        except Exception as e:
            logger.error(f"Failed to process file {upload_file.filename}: {e}")
            file_result["status"] = "error"
            file_result["error"] = str(e)
            files_failed += 1

        results.append(file_result)

    # Update repository counts
    try:
        await repository_store.update_counts(
            repo_id=repository_id,
            file_count=(repo.get("file_count", 0) or 0) + files_processed,
            node_count=(repo.get("node_count", 0) or 0) + total_nodes_created,
        )
    except Exception as e:
        logger.warning(f"Failed to update repository counts: {e}")

    return {
        "project_id": project_id,
        "repository_id": repository_id,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "total_nodes_created": total_nodes_created,
        "results": results,
    }


@router.get("/config")
async def get_upload_config() -> Dict[str, Any]:
    """
    Get file upload configuration.

    Returns current settings for allowed file extensions and size limits.
    Frontend can use this to display/validate before upload.
    """
    return {
        "allowed_extensions": list(get_allowed_extensions()),
        "max_file_size_mb": config.UPLOAD_MAX_FILE_SIZE_MB,
        "max_file_size_bytes": MAX_FILE_SIZE,
        "upload_directory": config.UPLOAD_BASE_DIR,
    }


@router.put("/config")
async def update_upload_config(
    allowed_extensions: Optional[List[str]] = None,
    max_file_size_mb: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Update file upload configuration.

    Note: Changes are runtime-only and will reset on server restart.
    For persistent changes, update environment variables.

    Args:
        allowed_extensions: List of file extensions (e.g., [".sql", ".py"])
        max_file_size_mb: Maximum file size in MB

    Returns:
        Updated configuration
    """
    global MAX_FILE_SIZE

    if allowed_extensions is not None:
        # Validate extensions start with dot
        validated = []
        for ext in allowed_extensions:
            ext = ext.strip().lower()
            if not ext.startswith("."):
                ext = "." + ext
            validated.append(ext)
        config.ALLOWED_FILE_EXTENSIONS = validated
        logger.info(f"Updated allowed extensions: {validated}")

    if max_file_size_mb is not None:
        if max_file_size_mb < 1 or max_file_size_mb > 500:
            raise HTTPException(
                status_code=400,
                detail="max_file_size_mb must be between 1 and 500"
            )
        config.UPLOAD_MAX_FILE_SIZE_MB = max_file_size_mb
        MAX_FILE_SIZE = max_file_size_mb * 1024 * 1024
        logger.info(f"Updated max file size: {max_file_size_mb}MB")

    return await get_upload_config()
