# Change: Align Frontend With Backend API & Complete UI Wiring

## Why
- Frontend calls outdated endpoints (e.g., lineage `/api/lineage/*`) that 404 on the backend and force mock data.
- Files UI depends on missing hooks and stub backend endpoints, so the file browser and stats cannot reflect reality.
- Upload and GitHub ingestion skip chunking/embedding for vector search and do not parse Python into the graph.
- Admin restart will be locked down in the backend; the Settings UI needs auth/flag awareness to avoid failing or issuing forbidden calls.
- Chat UX is non-streaming and cannot opt out of memory; local Ollama users need faster responses and clearer context handling.
- Dashboard and database views need health warnings when FastAPI/DuckDB/Neo4j/Qdrant/Ollama are unavailable.

## What Changes
- Align frontend endpoints with backend (`/api/v1/lineage/*`, configurable upload path, restart endpoint handling).
- Implement DuckDB-backed file list/stats/search/recent endpoints with full metadata (run_id, source, relative_path, status).
- Preserve relative paths for folder uploads and GitHub ingestion; surface paths in file listings.
- Apply chunking/embedding/indexing to upload and GitHub ingestion, and add Python graph extraction.
- Wire Files, Dashboard, and Database pages to backend APIs; remove mock data when backend is reachable.
- Add restart auth/header support and graceful handling when restart is disabled or requires auth.
- Add chat streaming (SSE) option for deep mode and a skip-memory flag for faster first responses; expose a “local/Ollama” preset with guidance on context length.
- Surface `/health` warnings in the UI when dependencies are degraded or unreachable.

## Impact
- Affected specs: `api-endpoints`, `ui-experience`, `data-organization`, `llm-service`, `websocket-dashboard`, `frontend-wiring`
- Affected code: `src/api/routers/files.py`, `src/api/routers/github.py`, `src/api/routers/ingest.py`, `src/api/routers/admin.py`, `src/storage/*`, `src/pages/Files.tsx`, `src/pages/Chat.tsx`, new frontend hooks/pages
- Dependencies: DuckDB, FastAPI, Neo4j, Qdrant, Ollama (UI must warn if unavailable)
