## Context
Define an ingestion log index entry stored alongside run artifacts for fast listing and retrieval.

## Decisions
- Use a JSON index file per run directory (e.g., ingestion_index.json) that is updated when ingestion completes.
- List endpoint scans index files under STORAGE_PATH with optional filtering for local environments.
- Include project_status in index entries to support active/inactive filtering on the log page.

## Risks / Trade-offs
- Filesystem scanning could be slower with large archives; mitigated by limiting results and supporting filters.

## Migration Plan
- Existing runs without index files are ignored until new runs are created.

## Open Questions
- Should ingestion index entries also be stored in DuckDB for faster queries later?
