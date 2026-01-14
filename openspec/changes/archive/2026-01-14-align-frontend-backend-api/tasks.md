# Implementation Tasks

## 1. Endpoint Alignment
- [x] 1.1 Update lineage fetch/search/node calls to `/api/v1/lineage/*` (configurable via Settings endpoints).
- [x] 1.2 Use configured upload endpoint from Settings for file uploads.
- [x] 1.3 Add restart auth/header support; handle 401/403/404/disabled states gracefully.

## 2. Backend File Metadata and Ingestion
- [x] 2.1 Implement DuckDB-backed `/api/v1/files`, `/api/v1/files/stats`, `/api/v1/files/search`, `/api/v1/files/recent` with filtering/pagination.
- [x] 2.2 Persist file metadata (relative_path, file_type, source, run_id, status, timestamps) for upload and GitHub ingestion.
- [x] 2.3 Preserve relative paths for folder uploads and GitHub ingestion; store under `run_dir/raw_source/<relative_path>`.
- [x] 2.4 Apply semantic chunking + embedding + indexing for upload and GitHub ingestion (LlamaIndex or legacy).
- [x] 2.5 Add Python graph extraction during ingestion and log chunking/indexing stages.

## 3. Frontend Wiring
- [x] 3.1 Implement shared hooks for files/stats/health and API settings.
- [x] 3.2 Wire Files page to backend endpoints and drop mock data when backend is reachable.
- [x] 3.3 Add Dashboard page wired to `/api/v1/stats` and `/api/v1/config/websocket` with connection state.
- [x] 3.4 Add Database page wired to lineage endpoints and file metadata so SQL/Python assets are visible.
- [x] 3.5 Surface `/health` warnings and disable actions when dependencies are down.

## 4. Chat Performance & Context
- [x] 4.1 Add SSE streaming option for deep chat (`/api/chat/deep/stream`) with UI toggle.
- [x] 4.2 Add skip-memory flag toggle for faster first responses; pass through to backend.
- [x] 4.3 Surface “local/Ollama mode” guidance: context-length expectations and model hints when users choose streaming/skip-memory.

## 5. Validation
- [x] 5.1 Add tests for file endpoints and ingestion pipeline integration.
- [x] 5.2 Run `openspec validate align-frontend-backend-api --strict`.

## 6. Chat Contract Alignment
- [x] 6.1 Implement OpenRouter chat gateway with fallback and JSON mapping.
- [x] 6.2 Map evidence IDs to URN scheme and add Qdrant chunk lookup endpoint.
- [x] 6.3 Expose chat model mappings in `/api/v1/config`.
