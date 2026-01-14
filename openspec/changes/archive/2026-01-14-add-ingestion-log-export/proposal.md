# Change: Add Ingestion Log Export and Verbose Session Logging

## Why
Ingestion progress is visible in real time but there is no durable log that can be retrieved later for debugging. Users need a per-ingestion log that can be exported and a way to enable verbose logging only when needed.

## What Changes
- Persist ingestion telemetry events to a JSONL log file per session.
- Add an optional verbose flag to ingestion requests (upload and GitHub) that records extra debug events.
- Add an API endpoint to retrieve or download ingestion logs by ingestion_id.

## Impact
- Affected specs: logging, api-endpoints
- Affected code: src/services/ingestion_tracker.py, src/api/routers/files.py, src/api/routers/github.py, new ingestion log router, src/api/main_local.py
