"""Ingestion endpoints for processing files and SQL."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..config import config
from ..models.ingest import IngestRequest, SqlIngestRequest

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/v1/ingest", tags=["ingestion"])


def get_app_state() -> Any:
    """Get application state from FastAPI app.

    This is a placeholder that will be replaced with actual state injection.
    The state will be passed via dependency injection in main.py.
    """
    # This will be replaced with proper dependency injection
    from ..main_local import state

    return state


@router.post("/sql")
async def ingest_sql(request: SqlIngestRequest) -> Dict[str, str]:
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
    state = get_app_state()

    if not state.extractor:
        raise HTTPException(status_code=503, detail="Graph Extractor not initialized")

    try:
        state.extractor.ingest_sql_lineage(
            sql_content=request.sql_content,
            dialect=request.dialect,
            source_file=request.source_file,
        )
        return {"status": "success", "source": request.source_file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest SQL: {e}")


@router.post("")
async def ingest_file(
    request: IngestRequest, background_tasks: BackgroundTasks
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
        HTTPException: If file is not found.
    """
    state = get_app_state()

    # Check file exists
    file_path = Path(request.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail=f"File not found: {request.file_path}"
        )

    async def do_ingest(file_path: str, file_type: str):
        """Background ingestion task.

        Args:
            file_path: Path to file to ingest.
            file_type: Type of file (sql, python, etc.).
        """
        # Import chunker
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.ingestion.semantic_chunker import SemanticChunker

        chunker = SemanticChunker()

        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Chunk it
        chunks = chunker.chunk_file(content, file_path)

        # Use LlamaIndex for indexing if available
        if config.USE_LLAMAINDEX and state.llamaindex_service:
            try:
                print(f"[*] Indexing {len(chunks)} chunks using LlamaIndex...")
                result = await state.llamaindex_service.index_code_chunks(chunks)
                print(
                    f"✅ LlamaIndex indexed {result['total_documents']} documents from {file_path}"
                )
            except Exception as e:
                print(f"[!] LlamaIndex indexing failed: {e}")
                print("[*] Falling back to legacy ingestion...")
                # Fall back to legacy method below
                config.USE_LLAMAINDEX = False

        # Legacy ingestion (fallback or when LlamaIndex disabled)
        if not config.USE_LLAMAINDEX or not state.llamaindex_service:
            for i, chunk in enumerate(chunks):
                try:
                    embedding = await state.ollama.embed(chunk.to_embedding_text())

                    await state.qdrant.upsert(
                        collection="code_chunks",
                        points=[
                            {
                                "id": hash(f"{file_path}_{i}")
                                % (10**12),  # Qdrant needs int IDs
                                "vector": embedding,
                                "payload": {
                                    "content": chunk.content,
                                    "file_path": str(chunk.file_path),
                                    "chunk_type": chunk.chunk_type.value,
                                    "tables": chunk.tables_referenced,
                                    "columns": chunk.columns_referenced,
                                },
                            }
                        ],
                    )
                except Exception as e:
                    print(f"Error processing chunk {i}: {e}")

            print(f"✅ Ingested {len(chunks)} chunks from {file_path} (legacy mode)")

        # Add entities to graph (regardless of indexing method)
        for chunk in chunks:
            for table in chunk.tables_referenced:
                try:
                    state.graph.add_entity(
                        entity_id=table.lower().replace(".", "_"),
                        entity_type="Table",
                        name=table,
                        source_file=str(file_path),
                    )
                except Exception as e:
                    print(f"Error adding entity {table}: {e}")

    background_tasks.add_task(do_ingest, str(file_path), request.file_type)

    return {"status": "accepted", "file": str(file_path)}
