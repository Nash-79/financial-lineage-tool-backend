# Change: Add Upload Ingestion Telemetry

## Why
File uploads currently complete without real-time progress events, so the frontend cannot show stage-based telemetry or surface failures clearly. GitHub ingestion already emits telemetry; uploads should behave the same.

## What Changes
- Emit ingestion_started/ingestion_progress/ingestion_complete events for file uploads using the ingestion tracker.
- Record per-file status transitions (saving, parsing, extracting) and errors for uploads.
- Return an `ingestion_id` with upload responses for correlation and diagnostics.

## Impact
- Affected specs: websocket-dashboard, api-endpoints
- Affected code: src/api/routers/files.py, src/services/ingestion_tracker.py
