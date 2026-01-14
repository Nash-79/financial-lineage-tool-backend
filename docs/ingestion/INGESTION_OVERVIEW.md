# Ingestion Overview

This document describes the current run-scoped ingestion pipeline.

## 1. Entry points

- `POST /api/v1/ingest` for file ingestion (path-based).
- `POST /api/v1/ingest/sql` for raw SQL ingestion (string payload).

For API details, see `../api/API_REFERENCE.md`.

## 2. Run-scoped storage layout

Every ingestion creates a run directory:

```
data/{project}/{YYYYMMDD_HHMMSS}_{seq}_{action}/
```

Run artifacts are stored under this directory:

- `raw_source/` - copy of the ingested file
- `chunks/` - semantic chunks created by `SemanticChunker`
- `embeddings/` - legacy embeddings JSONL (if legacy indexing is used)
- `validations/` - validation reports for parser/graph consistency
- `KG/` - Neo4j snapshots (pre/post ingestion)
- `ingestion_index.json` and `ingestion_{id}.jsonl` - ingestion logs

## 3. Pipeline stages (file ingestion)

1. **Run creation**: `ArtifactManager.create_run(...)` creates the run folder.
2. **Pre-ingestion snapshot**: `GraphSnapshotManager` exports a scoped Neo4j JSON
   snapshot to `KG/` (`phase=pre`).
3. **Graph ingestion**: SQL/Python/JSON are parsed into a `LineageResult`, then
   written to Neo4j by `GraphExtractor`.
4. **Chunking + vector indexing**:
   - `SemanticChunker` writes chunk files under `chunks/`.
   - LlamaIndex or legacy embedding pipeline writes to Qdrant.
5. **Validation**: `ValidationAgent` compares parser expectations vs Neo4j and
   writes `validations/{file}_validation.json`.
6. **KG enrichment**: `KGEnrichmentAgent` proposes LLM edges and writes them
   to Neo4j (`source="llm"`, `status="proposed"`).
7. **Post-ingestion snapshot**: Neo4j snapshot exported to `KG/` (`phase=post`).
8. **Artifact validation**: ingestion logs record missing artifacts.

## 4. Legacy organizer pipeline

The SQL organizer and file watcher (`data/raw` -> `data/separated_sql`) are still
available, but they are separate from the run-scoped ingestion pipeline above.
See `legacy/SQL_ORGANIZER_QUICKSTART.md` and
`legacy/FILE_WATCHER_GUIDE.md` for that legacy workflow.

