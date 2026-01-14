"""
Shared chunking and indexing pipeline for file ingestion.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..api.config import config
from ..ingestion.semantic_chunker import SemanticChunker

logger = logging.getLogger(__name__)


async def purge_before_ingest(
    *,
    file_path: str,
    state: Any,
    tracker: Optional[Any] = None,
    ingestion_id: Optional[str] = None,
    project_id: Optional[str] = None,
    repository_id: Optional[str] = None,
    collection: str = "code_chunks",
    stage: str = "purge",
) -> Dict[str, Any]:
    """Purge existing graph and vector data for a file before ingesting."""
    if tracker and ingestion_id:
        await tracker.log_stage(
            ingestion_id,
            stage=stage,
            status="started",
            file_path=file_path,
        )

    deleted = {"qdrant_deleted": 0, "neo4j_deleted": 0}

    if state.qdrant:
        result = await state.qdrant.delete_by_file_path(
            collection,
            file_path,
            project_id=project_id,
            repository_id=repository_id,
        )
        deleted["qdrant_deleted"] = result.get("deleted", 0)

    if state.graph:
        deleted["neo4j_deleted"] = state.graph.purge_file_assets(
            file_path,
            project_id=project_id,
            repository_id=repository_id,
        )

    if tracker and ingestion_id:
        await tracker.log_stage(
            ingestion_id,
            stage=stage,
            status="completed",
            file_path=file_path,
            summary=deleted,
        )

    return deleted


async def index_file_content(
    *,
    content: str,
    file_path: str,
    state: Any,
    tracker: Optional[Any] = None,
    ingestion_id: Optional[str] = None,
    project_id: Optional[str] = None,
    repository_id: Optional[str] = None,
    source: Optional[str] = None,
    dialect: str = "auto",
    chunk_output_dir: Optional[str] = None,
    embeddings_output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Chunk and index file content using LlamaIndex or legacy vector ingestion.

    Returns a summary dict with chunk count, indexed count, mode, and error.
    """
    chunker = SemanticChunker(dialect=dialect)
    if tracker and ingestion_id:
        await tracker.log_stage(
            ingestion_id,
            stage="chunking",
            status="started",
            file_path=file_path,
        )

    chunks = chunker.chunk_file(content, file_path)

    # Save chunks to disk (User Requirement: Visual "Split by Object")
    try:
        from pathlib import Path

        # Create 'chunks' directory relative to the source file
        source_path = Path(file_path)

        # PROPOSAL: Always save chunks alongside the input file (or in a sibling folder)
        # User requested: "under each Ingestion folder"
        # If file is in .../Ingestion_ID/subfolder/file.sql, we probably want .../Ingestion_ID/chunks/...
        # BUT for simplicity and robustness, let's put it in the same folder as the file for now,
        # or exactly as the user asked: "under each Ingestion folder"

        # If we assume the file IS in the ingestion folder (or a subfolder of it),
        # and we want to keep it clean:
        if chunk_output_dir:
            chunks_dir = Path(chunk_output_dir)
        else:
            chunks_dir = source_path.parent / "chunks"

        chunks_dir.mkdir(parents=True, exist_ok=True)

        # Save each chunk
        for i, chunk in enumerate(chunks):
            # Analyze content to determine folder and filename
            lines = chunk.content.strip().split("\n")
            first_line = lines[0] if lines else ""

            safe_name = "unknown"
            obj_type = "MISC"

            # Heuristic for type and name
            if (
                "CREATE OR REPLACE FUNCTION" in first_line
                or "CREATE OR ALTER FUNCTION" in first_line
                or "CREATE FUNCTION" in first_line
            ):
                obj_type = "FUNCTION"
                try:
                    safe_name = first_line.split("FUNCTION")[1].split("(")[0].strip()
                except:
                    safe_name = "func"
            elif "CREATE TABLE" in first_line:
                obj_type = "TABLE"
                try:
                    safe_name = first_line.split("TABLE")[1].split("(")[0].strip()
                except:
                    safe_name = "table"
            elif (
                "CREATE OR REPLACE VIEW" in first_line
                or "CREATE OR ALTER VIEW" in first_line
                or "CREATE VIEW" in first_line
            ):
                obj_type = "VIEW"
                try:
                    safe_name = first_line.split("VIEW")[1].split()[0].strip()
                except:
                    safe_name = "view"
            elif (
                "CREATE OR REPLACE PROCEDURE" in first_line
                or "CREATE OR ALTER PROCEDURE" in first_line
                or "CREATE PROCEDURE" in first_line
            ):
                obj_type = "PROCEDURE"
                try:
                    safe_name = first_line.split("PROCEDURE")[1].split()[0].strip()
                except:
                    safe_name = "proc"
            elif (
                "CREATE OR REPLACE TRIGGER" in first_line
                or "CREATE OR ALTER TRIGGER" in first_line
                or "CREATE TRIGGER" in first_line
            ):
                obj_type = "TRIGGER"
                try:
                    safe_name = first_line.split("TRIGGER")[1].split()[0].strip()
                except:
                    safe_name = "trigger"
            elif "SCHEMA" in first_line:
                obj_type = "SCHEMA"
                safe_name = "schema_definition"
            elif "chunk_type" in dir(chunk) and chunk.chunk_type.name.startswith(
                "PYTHON"
            ):
                obj_type = "PYTHON"
                # Use function name or class name if available
                if chunk.functions_defined:
                    safe_name = chunk.functions_defined[0]
                else:
                    safe_name = "".join(
                        c for c in first_line[:30] if c.isalnum() or c == "_"
                    )
            else:
                # Use first few words
                safe_name = "".join(
                    c for c in first_line[:30] if c.isalnum() or c == "_"
                )

            # Create hierarchy: chunks/{source_filename}/{object_type}/
            source_stem = Path(file_path).stem
            type_dir = chunks_dir / source_stem / obj_type
            type_dir.mkdir(parents=True, exist_ok=True)

            # Clean filename
            safe_name = "".join(
                c for c in safe_name if c.isalnum() or c in ("_", "-", ".")
            )
            safe_name = safe_name.strip("._-") or f"chunk_{i}"

            filename = f"{safe_name}.sql"

            with open(type_dir / filename, "w", encoding="utf-8") as f:
                f.write(f"-- Source: {file_path}\n")
                f.write(f"-- Type: {chunk.chunk_type.name}\n")
                f.write(f"-- Chunk: {i}\n")
                f.write("-" * 40 + "\n")
                f.write(chunk.content)

        logger.info(f"Saved {len(chunks)} chunks to {chunks_dir}/{source_stem}")

    except Exception as e:
        logger.warning(f"Failed to save chunks to disk: {e}")

    if tracker and ingestion_id:
        await tracker.log_stage(
            ingestion_id,
            stage="chunking",
            status="completed",
            file_path=file_path,
            summary={"chunks_created": len(chunks)},
        )

    if not chunks:
        return {
            "chunks": 0,
            "indexed": 0,
            "mode": "skipped",
            "error": "no_chunks_generated",
        }

    if config.USE_LLAMAINDEX and state.llamaindex_service:
        if tracker and ingestion_id:
            await tracker.log_stage(
                ingestion_id,
                stage="indexing",
                status="started",
                file_path=file_path,
                summary={"mode": "llamaindex"},
            )
        try:
            result = await state.llamaindex_service.index_code_chunks(chunks)
            indexed = int(result.get("total_documents", len(chunks)))
            if tracker and ingestion_id:
                await tracker.log_stage(
                    ingestion_id,
                    stage="indexing",
                    status="completed",
                    file_path=file_path,
                    summary={
                        "mode": "llamaindex",
                        "chunks_indexed": indexed,
                    },
                )
            return {
                "chunks": len(chunks),
                "indexed": indexed,
                "mode": "llamaindex",
                "error": None,
                "embeddings_path": None,
            }
        except Exception as exc:
            logger.warning("LlamaIndex indexing failed for %s: %s", file_path, exc)
            if tracker and ingestion_id:
                await tracker.log_stage(
                    ingestion_id,
                    stage="indexing",
                    status="failed",
                    file_path=file_path,
                    error=str(exc),
                )

    if not state.ollama or not state.qdrant:
        message = "vector services unavailable"
        if tracker and ingestion_id:
            await tracker.log_stage(
                ingestion_id,
                stage="indexing",
                status="skipped",
                file_path=file_path,
                error=message,
            )
            return {
                "chunks": len(chunks),
                "indexed": 0,
                "mode": "skipped",
                "error": message,
                "embeddings_path": None,
            }

    if tracker and ingestion_id:
        await tracker.log_stage(
            ingestion_id,
            stage="indexing",
            status="started",
            file_path=file_path,
            summary={"mode": "legacy"},
        )

    indexed = 0
    embeddings_path = None
    embeddings_handle = None
    try:
        if embeddings_output_dir:
            embeddings_dir = Path(embeddings_output_dir)
            embeddings_dir.mkdir(parents=True, exist_ok=True)
            safe_name = (
                str(file_path).replace("/", "_").replace("\\", "_").replace(":", "_")
            )
            embeddings_path = embeddings_dir / f"{safe_name}_embeddings.jsonl"
            embeddings_handle = embeddings_path.open("w", encoding="utf-8")

        for i, chunk in enumerate(chunks):
            embedding = await state.ollama.embed(
                chunk.to_embedding_text(), model=config.EMBEDDING_MODEL
            )
            sparse_vector = None
            if config.ENABLE_HYBRID_SEARCH:
                sparse_vector = state.qdrant.build_sparse_vector(chunk.content)
            vector_payload = await state.qdrant.build_vectors_payload(
                collection="code_chunks",
                dense_vector=embedding,
                sparse_vector=sparse_vector,
            )
            payload = {
                "content": chunk.content,
                "file_path": str(chunk.file_path),
                "chunk_type": chunk.chunk_type.value,
                "tables": chunk.tables_referenced,
                "columns": chunk.columns_referenced,
                "language": chunk.language,
            }
            if project_id:
                payload["project_id"] = project_id
            if repository_id:
                payload["repository_id"] = repository_id
            if source:
                payload["source"] = source

            point_id = hash(f"{file_path}_{i}") % (10**12)

            if embeddings_handle:
                record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "file_path": str(file_path),
                    "chunk_index": i,
                    "vector_id": point_id,
                    "embedding_model": config.EMBEDDING_MODEL,
                    "payload": payload,
                    "vector_payload": vector_payload,
                }
                embeddings_handle.write(json.dumps(record, ensure_ascii=False) + "\n")

            await state.qdrant.upsert(
                collection="code_chunks",
                points=[
                    {
                        "id": point_id,
                        **vector_payload,
                        "payload": payload,
                    }
                ],
            )
            indexed += 1
    except Exception as exc:
        logger.warning("Legacy indexing failed for %s: %s", file_path, exc)
        if tracker and ingestion_id:
            await tracker.log_stage(
                ingestion_id,
                stage="indexing",
                status="failed",
                file_path=file_path,
                error=str(exc),
            )
        return {
            "chunks": len(chunks),
            "indexed": indexed,
            "mode": "legacy",
            "error": str(exc),
            "embeddings_path": str(embeddings_path) if embeddings_path else None,
        }
    finally:
        if embeddings_handle:
            embeddings_handle.close()

    if tracker and ingestion_id:
        await tracker.log_stage(
            ingestion_id,
            stage="indexing",
            status="completed",
            file_path=file_path,
            summary={
                "mode": "legacy",
                "chunks_indexed": indexed,
            },
        )

    return {
        "chunks": len(chunks),
        "indexed": indexed,
        "mode": "legacy",
        "error": None,
        "embeddings_path": str(embeddings_path) if embeddings_path else None,
    }
