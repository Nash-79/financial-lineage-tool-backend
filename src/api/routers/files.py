"""
Files router for file upload and management.

Provides endpoints for uploading files with project scoping.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, Depends
from pydantic import BaseModel

from src.storage import ArtifactManager
from src.storage.graph_snapshot import GraphSnapshotManager
from src.storage.metadata_store import ProjectStore, RepositoryStore
from src.storage.upload_settings import UploadSettingsStore
from src.utils.file_metadata import infer_file_type, sanitize_relative_path
from src.services.ingestion_tracker import get_tracker, FileStatus
from src.services.ingestion_pipeline import index_file_content, purge_before_ingest
from src.config.sql_dialects import format_dialect_error, validate_dialect
from src.utils.audit_logger import get_audit_logger
from ..config import config
from ..middleware.auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/files",
    tags=["files"],
    dependencies=[Depends(get_current_user)],
)

# Store instances
project_store = ProjectStore()
repository_store = RepositoryStore()
artifact_manager = ArtifactManager(base_path="data")

# Maximum file size (50MB by default)
MAX_FILE_SIZE = config.UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024


class UploadConfigUpdate(BaseModel):
    """Request model for updating upload configuration."""

    allowed_extensions: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None


def get_allowed_extensions() -> set:
    """Get allowed file extensions from config."""
    return set(ext.strip() for ext in config.ALLOWED_FILE_EXTENSIONS)


def get_app_state() -> Any:
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in get_allowed_extensions()


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    project_id: str = Form(..., description="Project ID (required)"),
    repository_id: Optional[str] = Form(
        None, description="Repository ID (optional, creates new if omitted)"
    ),
    repository_name: Optional[str] = Form(
        None, description="Repository name (required if repository_id omitted)"
    ),
    instructions: Optional[str] = Form(
        None, description="Optional instructions for lineage extraction"
    ),
    dialect: Optional[str] = Form("auto", description="SQL dialect for parsing"),
    verbose: Optional[bool] = Form(
        False, description="Enable verbose ingestion logging"
    ),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Upload files for ingestion with project scoping.

    Files are validated, sanitized, and saved to hierarchical run directory.
    Then they are processed for lineage extraction and tagged with
    project_id and repository_id.

    Args:
        files: List of files to upload
        project_id: Parent project ID (required)
        repository_id: Existing repository ID (optional)
        repository_name: Name for new repository (required if repository_id not provided)

    Returns:
        Dictionary with upload results for each file including run_id
    """
    # Validate project exists
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    dialect_value = (dialect or "auto").strip()
    if not validate_dialect(dialect_value):
        raise HTTPException(status_code=400, detail=format_dialect_error(dialect_value))

    # Get or create repository
    if repository_id:
        repo = repository_store.get(repository_id)
        if not repo:
            raise HTTPException(
                status_code=404, detail=f"Repository not found: {repository_id}"
            )
        if repo["project_id"] != project_id:
            raise HTTPException(
                status_code=400,
                detail=f"Repository {repository_id} does not belong to project {project_id}",
            )
    else:
        # Create new repository
        if not repository_name:
            raise HTTPException(
                status_code=400,
                detail="repository_name is required when repository_id is not provided",
            )
        repo = await repository_store.create(
            project_id=project_id,
            name=repository_name,
            source="upload",
            source_ref=f"upload/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        )
        repository_id = repo["id"]
        logger.info(f"Created repository {repository_id} for upload")

    # Create ingestion run for this upload batch
    action_name = repository_name or repo["name"] or "file_upload"
    run_context = await artifact_manager.create_run(
        project_id=project_id,
        project_name=project["name"],
        action=f"upload_{action_name}",
    )

    tracker = get_tracker()
    audit = get_audit_logger()
    normalized_files = []
    for upload_file in files:
        relative_path = sanitize_relative_path(upload_file.filename)
        normalized_files.append((upload_file, relative_path))
    file_paths = [relative_path for _, relative_path in normalized_files]
    session = await tracker.start_session(
        source="upload",
        project_id=project_id,
        repository_id=repository_id,
        file_paths=file_paths,
        log_dir=run_context.run_dir,
        verbose=bool(verbose),
        run_id=run_context.run_id,
        project_status=project.get("status", "active"),
    )
    await tracker.log_debug(
        session.ingestion_id,
        "run_context_created",
        {
            "run_id": run_context.run_id,
            "run_dir": str(run_context.run_dir),
        },
    )

    # Save instructions if provided
    if instructions:
        instructions_file = run_context.run_dir / "instructions.md"
        with open(instructions_file, "w", encoding="utf-8") as f:
            f.write(f"# Upload Instructions\n\n{instructions}\n")
        logger.info(f"Saved upload instructions to {instructions_file}")
        await tracker.log_debug(
            session.ingestion_id,
            "instructions_saved",
            {"path": str(instructions_file)},
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

    state = get_app_state()

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
                project_id=project_id,
                run_id=run_context.run_id,
                run_dir=run_context.run_dir,
                file_paths=file_paths,
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
                    "file_count": len(file_paths),
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

    # Process each file
    results = []
    total_nodes_created = 0
    files_processed = 0
    files_failed = 0
    files_skipped_duplicate = 0

    for upload_file, relative_path in normalized_files:
        file_result = {
            "filename": upload_file.filename,
            "relative_path": relative_path,
            "file_type": infer_file_type(relative_path),
            "status": "pending",
            "error": None,
            "nodes_created": 0,
            "saved_path": None,
        }
        file_id = None

        try:
            # Validate file extension
            if not validate_file_extension(relative_path):
                file_result["status"] = "error"
                file_result["error"] = (
                    f"Unsupported file type. Allowed: {', '.join(get_allowed_extensions())}"
                )
                files_failed += 1
                await tracker.file_error(
                    session.ingestion_id,
                    relative_path,
                    file_result["error"],
                )
                results.append(file_result)
                continue

            # Read file content
            content = await upload_file.read()
            await tracker.log_debug(
                session.ingestion_id,
                "file_loaded",
                {
                    "file": relative_path,
                    "size_bytes": len(content),
                },
            )

            # Validate file size
            if len(content) > MAX_FILE_SIZE:
                file_result["status"] = "error"
                file_result["error"] = (
                    f"File too large. Maximum size: {config.UPLOAD_MAX_FILE_SIZE_MB}MB"
                )
                files_failed += 1
                await tracker.file_error(
                    session.ingestion_id,
                    relative_path,
                    file_result["error"],
                )
                results.append(file_result)
                continue

            try:
                content_str = content.decode("utf-8")
            except UnicodeDecodeError:
                content_str = content.decode("utf-8", errors="replace")

            filename = Path(relative_path).name
            file_path = raw_source_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Save file to run directory
            with open(file_path, "wb") as f:
                f.write(content)

            file_result["saved_path"] = str(file_path)
            logger.info(f"Saved uploaded file: {file_path}")
            await tracker.log_debug(
                session.ingestion_id,
                "file_saved",
                {
                    "file": relative_path,
                    "path": str(file_path),
                },
            )

            # Register file with content hashing and deduplication
            registration = await artifact_manager.register_file(
                project_id=project_id,
                run_id=run_context.run_id,
                filename=filename,
                file_path=file_path,
                relative_path=relative_path,
                file_type=infer_file_type(relative_path),
                source="upload",
                repository_id=repository_id,
                status="pending",
            )
            file_id = registration.get("file_id")

            file_result["file_hash"] = registration["file_hash"]
            file_result["file_status"] = registration["status"]
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
                await tracker.file_skipped(
                    session.ingestion_id,
                    relative_path,
                    reason="duplicate",
                )
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

            # Process file for lineage extraction
            nodes_created = 0
            ext = Path(relative_path).suffix.lower()
            plugin = None

            await purge_before_ingest(
                file_path=relative_path,
                state=state,
                tracker=tracker,
                ingestion_id=session.ingestion_id,
                project_id=project_id,
                repository_id=repository_id,
            )

            if state.parser and state.extractor:
                try:
                    # Parse file
                    await tracker.update_file_status(
                        session.ingestion_id,
                        relative_path,
                        FileStatus.PARSING,
                    )
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
                        await tracker.update_file_status(
                            session.ingestion_id,
                            relative_path,
                            FileStatus.EXTRACTING,
                        )

                        # Log lineage stage started (graph extraction)
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="lineage",
                            status="started",
                            file_path=relative_path,
                        )

                        if plugin:
                            result = plugin.parse(
                                content_str,
                                {"dialect": dialect_value, "file_path": relative_path},
                            )
                            nodes_created = state.extractor.ingest_lineage_result(
                                result,
                                project_id=project_id,
                                repository_id=repository_id,
                                source_file=relative_path,
                                source="upload",
                            )
                        else:
                            nodes_created = (
                                state.extractor.ingest_sql_lineage(
                                    sql_content=content_str,
                                    dialect=dialect_value,
                                    source_file=relative_path,
                                    project_id=project_id,
                                    repository_id=repository_id,
                                    source="upload",
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
                            session.ingestion_id,
                            relative_path,
                            FileStatus.EXTRACTING,
                        )
                        await tracker.log_stage(
                            session.ingestion_id,
                            stage="parsing",
                            status="started",
                            file_path=relative_path,
                        )
                        if plugin:
                            result = plugin.parse(
                                content_str,
                                {"file_path": relative_path},
                            )
                            nodes_created = state.extractor.ingest_lineage_result(
                                result,
                                project_id=project_id,
                                repository_id=repository_id,
                                source_file=relative_path,
                                source="upload",
                            )
                        else:
                            state.extractor.ingest_python(
                                content=content_str,
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
                            content_str,
                            {"file_path": relative_path},
                        )
                        nodes_created = state.extractor.ingest_lineage_result(
                            result,
                            project_id=project_id,
                            repository_id=repository_id,
                            source_file=relative_path,
                            source="upload",
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
                        await tracker.update_file_status(
                            session.ingestion_id,
                            relative_path,
                            FileStatus.COMPLETE,
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to extract lineage from {relative_path}: {e}"
                    )

                    # Log stage failure
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="parsing",
                        status="failed",
                        file_path=relative_path,
                        error=str(e),
                    )

                    file_result["status"] = "error"
                    file_result["error"] = str(e)
                    files_failed += 1
                    if file_id:
                        await artifact_manager.update_file_status(file_id, "error")
                    await tracker.file_error(
                        session.ingestion_id,
                        relative_path,
                        str(e),
                    )
                    results.append(file_result)
                    continue

            index_result = await index_file_content(
                content=content_str,
                file_path=relative_path,
                state=state,
                tracker=tracker,
                ingestion_id=session.ingestion_id,
                project_id=project_id,
                repository_id=repository_id,
                source="upload",
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
                    files_processed += 1
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
                files_failed += 1
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
                    content=content_str,
                    plugin=plugin,
                    file_path=relative_path,
                    project_id=project_id,
                    dialect=dialect_value if ext in {".sql", ".ddl"} else None,
                )
                validation_payload = validation_summary.to_dict()
                validation_payload["file_path"] = relative_path
                validation_payload["project_id"] = project_id
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
                snippet = content_str
                if len(snippet) > 8000:
                    snippet = snippet[:8000]
                kg_summary = await state.kg_agent.enrich_file(
                    code_snippet=snippet,
                    file_path=relative_path,
                    project_id=project_id,
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
            files_processed += 1
            await tracker.file_complete(
                session.ingestion_id,
                relative_path,
                nodes_created,
            )

        except Exception as e:
            logger.error(f"Failed to process file {relative_path}: {e}")
            file_result["status"] = "error"
            file_result["error"] = str(e)
            files_failed += 1
            if file_id:
                await artifact_manager.update_file_status(file_id, "error")
            await tracker.file_error(
                session.ingestion_id,
                relative_path,
                str(e),
            )

        results.append(file_result)
        try:
            audit.log_ingestion(
                user_id=user.user_id,
                file_path=relative_path,
                project_id=project_id,
                success=file_result.get("status") not in {"error"},
                error=file_result.get("error"),
            )
        except Exception:
            pass

    # Update repository counts
    try:
        await repository_store.update_counts(
            repo_id=repository_id,
            file_count=(repo.get("file_count", 0) or 0) + files_processed,
            node_count=(repo.get("node_count", 0) or 0) + total_nodes_created,
        )
    except Exception as e:
        logger.warning(f"Failed to update repository counts: {e}")

    # Mark run as completed
    run_status = "completed" if files_failed == 0 else "completed_with_errors"
    await artifact_manager.complete_run(
        run_id=run_context.run_id,
        status=run_status,
        error_message=f"{files_failed} files failed" if files_failed > 0 else None,
    )
    await tracker.complete_session(session.ingestion_id)

    return {
        "project_id": project_id,
        "repository_id": repository_id,
        "ingestion_id": session.ingestion_id,
        "run_id": run_context.run_id,
        "run_dir": str(run_context.run_dir),
        "snapshot": snapshot_info.__dict__ if snapshot_info else None,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "files_skipped_duplicate": files_skipped_duplicate,
        "total_nodes_created": total_nodes_created,
        "results": results,
    }


@router.get("")
async def list_files(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    repository_id: Optional[str] = Query(None, description="Filter by repository ID"),
    source: Optional[str] = Query(
        None, description="Filter by ingestion source (upload/github)"
    ),
    status: Optional[str] = Query(
        None, description="Filter by status (processed/pending/error/skipped)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> List[Dict[str, Any]]:
    """
    List ingested files from DuckDB metadata.

    Returns a flat list of file metadata records suitable for frontend
    tree reconstruction.
    """
    return artifact_manager.list_files(
        project_id=project_id,
        repository_id=repository_id,
        source=source,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_file_stats(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    repository_id: Optional[str] = Query(None, description="Filter by repository ID"),
    source: Optional[str] = Query(
        None, description="Filter by ingestion source (upload/github)"
    ),
) -> Dict[str, int]:
    """Return file counts by status from metadata store."""
    return artifact_manager.get_file_stats(
        project_id=project_id,
        repository_id=repository_id,
        source=source,
    )


@router.get("/search")
async def search_files(
    q: str = Query(..., description="Search query"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    repository_id: Optional[str] = Query(None, description="Filter by repository ID"),
    source: Optional[str] = Query(
        None, description="Filter by ingestion source (upload/github)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> List[Dict[str, Any]]:
    """Search files by filename or relative path."""
    return artifact_manager.search_files(
        query_text=q,
        project_id=project_id,
        repository_id=repository_id,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.get("/recent")
async def get_recent_files(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    repository_id: Optional[str] = Query(None, description="Filter by repository ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records"),
) -> List[Dict[str, Any]]:
    """Return recently updated files for dashboard widgets."""
    return artifact_manager.list_recent_files(
        project_id=project_id,
        repository_id=repository_id,
        limit=limit,
    )


@router.get("/config")
async def get_upload_config() -> Dict[str, Any]:
    """
    Get file upload configuration.

    Returns current settings for allowed file extensions and size limits.
    Frontend can use this to display/validate before upload.
    """
    # Try to load settings from database
    settings_store = UploadSettingsStore()
    db_settings = settings_store.get_settings()

    if db_settings:
        # Settings loaded from database
        extensions = json.loads(db_settings["allowed_extensions"])
        return {
            "allowed_extensions": extensions,
            "max_file_size_mb": db_settings["max_file_size_mb"],
            "max_file_size_bytes": db_settings["max_file_size_mb"] * 1024 * 1024,
            "upload_directory": config.UPLOAD_BASE_DIR,
            "persisted": True,
            "last_updated": db_settings["updated_at"],
            "source": "database",
        }
    else:
        # Fallback to config (environment variables)
        return {
            "allowed_extensions": list(get_allowed_extensions()),
            "max_file_size_mb": config.UPLOAD_MAX_FILE_SIZE_MB,
            "max_file_size_bytes": MAX_FILE_SIZE,
            "upload_directory": config.UPLOAD_BASE_DIR,
            "persisted": False,
            "last_updated": None,
            "source": "environment",
        }


@router.put("/config")
async def update_upload_config(
    config_update: UploadConfigUpdate,
) -> Dict[str, Any]:
    """
    Update file upload configuration.

    Settings are persisted to database and survive server restarts.

    Args:
        config_update: Upload configuration updates (allowed_extensions, max_file_size_mb)

    Returns:
        Updated configuration with persistence confirmation
    """
    global MAX_FILE_SIZE

    # Get current settings
    current_extensions = list(get_allowed_extensions())
    current_size = config.UPLOAD_MAX_FILE_SIZE_MB

    # Validate and update extensions
    if config_update.allowed_extensions is not None:
        allowed_extensions = config_update.allowed_extensions
        validated = []
        for ext in allowed_extensions:
            ext = ext.strip().lower()
            if not ext.startswith("."):
                ext = "." + ext
            validated.append(ext)
        current_extensions = validated
        config.ALLOWED_FILE_EXTENSIONS = validated
        logger.info(f"Updated allowed extensions: {validated}")

    # Validate and update file size
    if config_update.max_file_size_mb is not None:
        max_file_size_mb = config_update.max_file_size_mb
        if max_file_size_mb < 1 or max_file_size_mb > 500:
            raise HTTPException(
                status_code=400, detail="max_file_size_mb must be between 1 and 500"
            )
        current_size = max_file_size_mb
        config.UPLOAD_MAX_FILE_SIZE_MB = max_file_size_mb
        MAX_FILE_SIZE = max_file_size_mb * 1024 * 1024
        logger.info(f"Updated max file size: {max_file_size_mb}MB")

    # Persist to database
    settings_store = UploadSettingsStore()
    success = await settings_store.save_settings(
        allowed_extensions=current_extensions,
        max_file_size_mb=current_size,
        updated_by="api",
    )

    if not success:
        logger.error("Failed to persist upload settings to database")
        raise HTTPException(
            status_code=500, detail="Failed to persist settings to database"
        )

    return await get_upload_config()
