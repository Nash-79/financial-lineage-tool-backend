## Context
The current UI relies on missing hooks and mock data, while backend file endpoints are placeholders.
Upload and GitHub ingestion only parse SQL/DDL into the graph and skip chunking/embedding for vector search and other file types.
Dashboard and database views need to reflect live backend state and warn when dependencies are unavailable.

## Goals / Non-Goals
- Goals:
  - Provide DuckDB-backed file list/stats/search endpoints with complete metadata.
  - Preserve folder structure metadata for uploads and GitHub ingestion.
  - Use the same chunking/embedding/indexing pipeline for upload and GitHub ingestion.
  - Wire Files, Dashboard, and Database UI to backend endpoints and show health warnings.
- Non-Goals:
  - Redesign frontend visuals or introduce new UI frameworks.
  - Replace the existing ingestion tracker or graph database.

## Decisions
- Decision: Compute file listings from DuckDB runs/files tables and expose a tree view option derived from relative paths.
- Decision: Capture folder upload relative paths from the browser (webkitRelativePath) and persist them in the metadata store.
- Decision: Reuse the semantic chunker and LlamaIndex/legacy ingestion path used by `/api/v1/ingest` for upload and GitHub ingestion.
- Decision: Surface backend readiness via `/health` and show warnings in UI when required services are down.

## Risks / Trade-offs
- Increased ingestion latency when chunking/embedding is added to upload and GitHub flows.
- Additional metadata fields may require migrations and backfill for existing records.
- UI warnings must avoid false positives when optional services are disabled.

## Migration Plan
- Add DuckDB columns for relative_path, file_type, and source metadata if missing.
- Backfill existing file records from run artifacts where possible.
- Roll out UI wiring behind a feature flag if needed, then remove mock data.

## Open Questions
- Should file list endpoints return a flat list by default or a tree view?
- Should Python extraction generate DataAsset nodes or only code entities?
