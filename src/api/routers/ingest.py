"""Ingestion endpoints for processing files and SQL."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends

from ..config import config
from ..models.ingest import IngestRequest, SqlIngestRequest, SqlIngestResponse
from ..middleware.auth import get_current_user, User
from src.utils.audit_logger import get_audit_logger
from src.services.ingestion_pipeline import index_file_content, purge_before_ingest
from src.config.sql_dialects import format_dialect_error, validate_dialect
from src.services.ingestion_tracker import get_tracker, FileStatus
from src.storage import ArtifactManager
from src.storage.graph_snapshot import GraphSnapshotManager
from src.storage.metadata_store import ProjectStore, ensure_default_project

if TYPE_CHECKING:
    pass

router = APIRouter(
    prefix="/api/v1/ingest",
    tags=["ingestion"],
    dependencies=[Depends(get_current_user)],
)

artifact_manager = ArtifactManager(base_path="data")
project_store = ProjectStore()


def get_app_state() -> Any:
    """Get application state from FastAPI app.

    This is a placeholder that will be replaced with actual state injection.
    The state will be passed via dependency injection in main.py.
    """
    # This will be replaced with proper dependency injection
    from ..main_local import state

    return state


@router.post("/sql", response_model=SqlIngestResponse)
async def ingest_sql(
    request: SqlIngestRequest, user: User = Depends(get_current_user)
) -> SqlIngestResponse:
    """Parse and ingest raw SQL string into the knowledge graph.

    Processes SQL content to extract lineage information and stores it
    in the Neo4j graph database.

    Args:
        request: SQL ingestion request with SQL content, dialect, and source file.

    Returns:
        Dictionary with status and source file information.

    Raises:
        HTTPException: If graph extractor is not initialized or ingestion fails.
    """
    import logging
    from src.llm.context_builder import build_context_block

    logger = logging.getLogger(__name__)
    state = get_app_state()

    if not state.extractor:
        raise HTTPException(status_code=503, detail="Graph Extractor not initialized")

    dialect_value = (request.dialect or "auto").strip() or "auto"
    if not validate_dialect(dialect_value):
        raise HTTPException(status_code=400, detail=format_dialect_error(dialect_value))

    # Build project context if project_id provided
    context_block = ""
    if request.project_id:
        try:
            context_block = build_context_block(request.project_id)
            if context_block:
                logger.info(f"Project context loaded for {request.project_id}")
                print(f"[Context] Using project context:\n{context_block}")
        except Exception as e:
            logger.error(f"Failed to build project context: {e}")
            print(f"[Context] Error building context: {e}")
            # Continue ingestion without context

    audit = get_audit_logger()
    try:
        await purge_before_ingest(
            file_path=request.source_file,
            state=state,
            project_id=request.project_id,
        )
        plugin = (
            state.plugin_registry.get_for_extension(".sql")
            if getattr(state, "plugin_registry", None)
            else None
        )
        if plugin:
            result = plugin.parse(
                request.sql_content,
                {"dialect": dialect_value, "file_path": request.source_file},
            )
            state.extractor.ingest_lineage_result(
                result,
                project_id=request.project_id,
                source_file=request.source_file,
                source="ingest_sql",
            )
        else:
            state.extractor.ingest_sql_lineage(
                sql_content=request.sql_content,
                dialect=dialect_value,
                source_file=request.source_file,
                project_id=request.project_id,
            )
        audit.log_ingestion(
            user_id=user.user_id,
            file_path=request.source_file,
            project_id=request.project_id,
            success=True,
        )
        return SqlIngestResponse(
            status="success",
            source=request.source_file,
            context_applied=bool(context_block),
        )
    except Exception as e:
        audit.log_ingestion(
            user_id=user.user_id,
            file_path=request.source_file,
            project_id=request.project_id,
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to ingest SQL: {e}")


@router.post(
    "",
    responses={
        200: {"description": "File accepted for ingestion"},
        404: {"description": "File not found at specified path"},
        422: {"description": "Validation error"},
    },
)
async def ingest_file(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Ingest a file for lineage analysis.

    Processes the file in the background, extracting code chunks and storing
    them in the vector database and knowledge graph. Supports both LlamaIndex
    and legacy ingestion methods.

    Args:
        request: Ingestion request with file path and file type.
        background_tasks: FastAPI background tasks for async processing.

    Returns:
        Dictionary with acceptance status and file path.

    Raises:
        HTTPException: If file is not found (404).
    """
    state = get_app_state()

    # Check file exists
    file_path = Path(request.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail=f"File not found: {request.file_path}"
        )

    dialect_value = (request.dialect or "auto").strip() or "auto"
    is_sql_file = request.file_type.lower() in {
        "sql",
        "ddl",
        "dml",
    } or file_path.suffix.lower() in {".sql", ".ddl", ".dml"}
    if is_sql_file and not validate_dialect(dialect_value):
        raise HTTPException(status_code=400, detail=format_dialect_error(dialect_value))

    project_id = request.project_id or "default"
    project = project_store.get(project_id)
    if not project and project_id == "default":
        project = await ensure_default_project()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    run_context = await artifact_manager.create_run(
        project_id=project_id,
        project_name=project["name"],
        action=f"ingest_{file_path.stem}",
    )
    raw_source_dir = run_context.get_artifact_dir("raw_source")
    raw_source_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = run_context.get_artifact_dir("chunks")
    chunks_dir.mkdir(parents=True, exist_ok=True)
    validations_dir = run_context.get_artifact_dir("validations")
    validations_dir.mkdir(parents=True, exist_ok=True)
    embeddings_dir = run_context.get_artifact_dir("embeddings")
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    tracker = get_tracker()
    source_identifier = str(file_path)
    session = await tracker.start_session(
        source="ingest",
        project_id=project_id,
        repository_id="manual",
        file_paths=[source_identifier],
        log_dir=run_context.run_dir,
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
                file_paths=[source_identifier],
                phase="pre",
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
                    "file_count": 1,
                },
            )
        except Exception as exc:
            await tracker.log_stage(
                session.ingestion_id,
                stage="graph_snapshot",
                status="failed",
                error=str(exc),
                summary={"project_name": project["name"]},
            )

    async def do_ingest(file_path: str, file_type: str):
        """Background ingestion task.

        Args:
            file_path: Path to file to ingest.
            file_type: Type of file (sql, python, etc.).
        """
        file_id = None
        parsing_failed = False
        parsing_error = None
        validation_path = None
        raw_source_path = None

        def _dir_has_files(path: Path) -> bool:
            if not path.exists():
                return False
            return any(entry.is_file() for entry in path.rglob("*"))

        try:
            raw_source_path = raw_source_dir / Path(file_path).name
            shutil.copy2(file_path, raw_source_path)
            await tracker.log_debug(
                session.ingestion_id,
                "file_saved",
                {"file": source_identifier, "path": str(raw_source_path)},
            )

            registration = await artifact_manager.register_file(
                project_id=project_id,
                run_id=run_context.run_id,
                filename=Path(file_path).name,
                file_path=raw_source_path,
                relative_path=source_identifier,
                file_type=file_type,
                source="ingest",
                repository_id=None,
                status="pending",
            )
            file_id = registration.get("file_id")
            if registration.get("skip_processing"):
                await tracker.file_skipped(
                    session.ingestion_id,
                    source_identifier,
                    reason="duplicate",
                )
                await artifact_manager.complete_run(
                    run_id=run_context.run_id,
                    status="completed",
                )
                await tracker.complete_session(session.ingestion_id)
                return

            await purge_before_ingest(
                file_path=source_identifier,
                state=state,
                tracker=tracker,
                ingestion_id=session.ingestion_id,
                project_id=project_id,
            )

            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read()

            ext = Path(file_path).suffix.lower()
            plugin = (
                state.plugin_registry.get_for_extension(ext)
                if getattr(state, "plugin_registry", None)
                else None
            )
            nodes_created = 0

            if state.extractor:
                await tracker.update_file_status(
                    session.ingestion_id,
                    source_identifier,
                    FileStatus.PARSING,
                )
                try:
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="parsing",
                        status="started",
                        file_path=source_identifier,
                    )
                    if plugin:
                        result = plugin.parse(
                            content,
                            {"dialect": dialect_value, "file_path": source_identifier},
                        )
                        nodes_created = state.extractor.ingest_lineage_result(
                            result,
                            project_id=project_id,
                            source_file=source_identifier,
                            source="ingest_file",
                        )
                        state.extractor.flush_batch()
                    elif ext in {".sql", ".ddl", ".dml"}:
                        nodes_created = (
                            state.extractor.ingest_sql_lineage(
                                sql_content=content,
                                dialect=dialect_value,
                                source_file=source_identifier,
                                project_id=project_id,
                                source="ingest_file",
                            )
                            or 0
                        )
                        state.extractor.flush_batch()
                    elif ext == ".py":
                        state.extractor.ingest_python(
                            content=content,
                            source_file=source_identifier,
                            project_id=project_id,
                        )
                        state.extractor.flush_batch()
                    elif ext == ".json":
                        state.extractor.ingest_json(
                            content=content,
                            source_file=source_identifier,
                            project_id=project_id,
                        )
                        state.extractor.flush_batch()

                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="parsing",
                        status="completed",
                        file_path=source_identifier,
                        summary={"nodes_created": nodes_created},
                    )
                except Exception as exc:
                    parsing_failed = True
                    parsing_error = str(exc)
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="parsing",
                        status="failed",
                        file_path=source_identifier,
                        error=str(exc),
                    )

            index_result = await index_file_content(
                content=content,
                file_path=source_identifier,
                state=state,
                tracker=tracker,
                ingestion_id=session.ingestion_id,
                project_id=project_id,
                source="ingest",
                dialect=dialect_value,
                chunk_output_dir=str(chunks_dir),
                embeddings_output_dir=str(embeddings_dir),
            )
            if index_result.get("error"):
                await tracker.log_stage(
                    session.ingestion_id,
                    stage="artifact_validation",
                    status="failed",
                    file_path=source_identifier,
                    summary={
                        "issues": ["indexing_failed"],
                        "error": index_result.get("error"),
                    },
                )
                await purge_before_ingest(
                    file_path=source_identifier,
                    state=state,
                    tracker=tracker,
                    ingestion_id=session.ingestion_id,
                    project_id=project_id,
                    stage="purge_cleanup",
                )
                if file_id:
                    await artifact_manager.update_file_status(file_id, "error")
                await tracker.file_error(
                    session.ingestion_id,
                    source_identifier,
                    index_result.get("error"),
                )
                await artifact_manager.complete_run(
                    run_id=run_context.run_id,
                    status="completed_with_errors",
                    error_message=index_result.get("error"),
                )
                await tracker.complete_session(session.ingestion_id)
                return

            if state.validation_agent:
                validation_summary = state.validation_agent.validate_content(
                    content=content,
                    plugin=plugin,
                    file_path=source_identifier,
                    project_id=project_id,
                    dialect=dialect_value if ext in {".sql", ".ddl", ".dml"} else None,
                )
                validation_payload = validation_summary.to_dict()
                validation_payload["file_path"] = source_identifier
                validation_payload["project_id"] = project_id
                validation_payload["ingestion_id"] = session.ingestion_id
                safe_validation_name = (
                    source_identifier.replace("/", "_")
                    .replace("\\", "_")
                    .replace(":", "_")
                )
                validation_filename = f"{safe_validation_name}_validation.json"
                validation_path = validations_dir / validation_filename
                try:
                    with validation_path.open("w", encoding="utf-8") as handle:
                        json.dump(
                            validation_payload, handle, indent=2, ensure_ascii=False
                        )
                except Exception as exc:
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="validation",
                        status="failed",
                        file_path=source_identifier,
                        error=str(exc),
                    )
                else:
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
                        file_path=source_identifier,
                        summary={
                            "status": validation_summary.status,
                            "missing_nodes": len(validation_summary.missing_nodes),
                            "missing_edges": len(validation_summary.missing_edges),
                            "artifact_path": str(validation_path),
                        },
                        error=validation_summary.error,
                    )

            if state.kg_agent:
                snippet = content if len(content) <= 8000 else content[:8000]
                kg_summary = await state.kg_agent.enrich_file(
                    code_snippet=snippet,
                    file_path=source_identifier,
                    project_id=project_id,
                    ingestion_id=session.ingestion_id,
                )
                await tracker.log_stage(
                    session.ingestion_id,
                    stage="kg_enrichment",
                    status="completed" if not kg_summary.error else "failed",
                    file_path=source_identifier,
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
                        file_paths=[source_identifier],
                        phase="post",
                    )
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="graph_snapshot_post",
                        status="completed",
                        summary={
                            "snapshot_path": snapshot_info.path,
                            "node_count": snapshot_info.node_count,
                            "edge_count": snapshot_info.edge_count,
                            "project_name": snapshot_info.project_name,
                            "file_count": 1,
                        },
                    )
                except Exception as exc:
                    await tracker.log_stage(
                        session.ingestion_id,
                        stage="graph_snapshot_post",
                        status="failed",
                        error=str(exc),
                        summary={"project_name": project["name"]},
                    )

            artifact_issues = []
            if raw_source_path is None or not raw_source_path.exists():
                artifact_issues.append("raw_source_missing")
            elif raw_source_path.stat().st_size == 0:
                artifact_issues.append("raw_source_empty")

            expected_chunks_root = chunks_dir / Path(file_path).stem
            if not _dir_has_files(expected_chunks_root):
                artifact_issues.append("chunks_missing")

            if state.validation_agent:
                if validation_path is None or not validation_path.exists():
                    artifact_issues.append("validation_missing")

            if parsing_failed:
                artifact_issues.append("parsing_failed")

            if index_result.get("mode") == "legacy":
                embeddings_path = index_result.get("embeddings_path")
                if not embeddings_path:
                    artifact_issues.append("embeddings_missing")
                else:
                    try:
                        path_obj = Path(embeddings_path)
                        if not path_obj.exists() or path_obj.stat().st_size == 0:
                            artifact_issues.append("embeddings_missing")
                    except Exception:
                        artifact_issues.append("embeddings_missing")

            await tracker.log_stage(
                session.ingestion_id,
                stage="artifact_validation",
                status="failed" if artifact_issues else "completed",
                file_path=source_identifier,
                summary={
                    "issues": artifact_issues,
                    "parsing_error": parsing_error,
                },
            )

            if artifact_issues:
                await purge_before_ingest(
                    file_path=source_identifier,
                    state=state,
                    tracker=tracker,
                    ingestion_id=session.ingestion_id,
                    project_id=project_id,
                    stage="purge_cleanup",
                )
                if file_id:
                    await artifact_manager.update_file_status(file_id, "error")
                await tracker.file_error(
                    session.ingestion_id,
                    source_identifier,
                    "artifact_validation_failed",
                )
                await artifact_manager.complete_run(
                    run_id=run_context.run_id,
                    status="completed_with_errors",
                    error_message="artifact validation failed",
                )
                await tracker.complete_session(session.ingestion_id)
                return

            if file_id:
                await artifact_manager.mark_file_processed(file_id)
            await tracker.file_complete(
                session.ingestion_id,
                source_identifier,
                nodes_created,
            )
            await artifact_manager.complete_run(
                run_id=run_context.run_id,
                status="completed",
            )
            await tracker.complete_session(session.ingestion_id)
        except Exception as exc:
            if file_id:
                await artifact_manager.update_file_status(file_id, "error")
            await tracker.file_error(
                session.ingestion_id,
                source_identifier,
                str(exc),
            )
            await artifact_manager.complete_run(
                run_id=run_context.run_id,
                status="completed_with_errors",
                error_message=str(exc),
            )
            await tracker.complete_session(session.ingestion_id)

    background_tasks.add_task(do_ingest, str(file_path), request.file_type)

    return {
        "status": "accepted",
        "file": str(file_path),
        "project_id": project_id,
        "run_id": run_context.run_id,
        "ingestion_id": session.ingestion_id,
        "run_dir": str(run_context.run_dir),
    }
