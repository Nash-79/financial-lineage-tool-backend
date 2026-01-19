## 1. Setup & Dependencies

- [x] 1.1 Add `loguru` to requirements.txt
- [x] 1.2 Remove `structlog` from requirements.txt (unused)
- [x] 1.3 Create `src/utils/loguru_config.py` with Loguru setup

## 2. Core Logging Infrastructure

- [x] 2.1 Implement Loguru configuration with environment variables
  - LOG_LEVEL, LOG_FORMAT (json/pretty), LOG_SINK (stdout/file/both)
  - LOG_PATH, LOG_RETENTION_DAYS
- [x] 2.2 Add request ID context filter/interceptor
- [x] 2.3 Add OpenTelemetry trace ID correlation (when OTEL enabled)
- [x] 2.4 Configure log rotation and compression (daily, gzip after 1 day)
- [x] 2.5 Suppress third-party library noise (httpx, httpcore, urllib3)

## 3. Compatibility Layer

- [x] 3.1 Create `logging` → Loguru intercept handler for gradual migration
- [x] 3.2 Test that existing `logging.getLogger()` calls work via intercept
- [ ] 3.3 Document migration pattern for developers

## 4. Unified Log Storage

- [x] 4.1 Create unified JSONL schema with common fields (timestamp, category, level, message, module, request_id, trace_id, extra)
- [x] 4.2 Create `src/utils/log_reader.py` - unified log reader for all categories
- [ ] 4.3 Migrate chat logs to JSONL format (`logs/chat/chat_{date}.jsonl`)
- [ ] 4.4 Consolidate ingestion logs with index file (`logs/ingestion/_index.jsonl`)
- [x] 4.5 Ensure audit logs maintain JSONL format (already compliant)
- [x] 4.6 Add category field to all log entries

## 5. Unified Log Viewer API

- [x] 5.1 Create `src/api/routers/logs.py` router
- [x] 5.2 Implement GET `/api/v1/logs/categories` - list all log categories with stats
- [x] 5.3 Implement GET `/api/v1/logs` - unified query across all categories
- [x] 5.4 Add filtering: category, level, module, time range, request_id
- [x] 5.5 Add filtering: ingestion_id, chat_id (cross-category correlation)
- [x] 5.6 Add full-text search capability
- [x] 5.7 Implement GET `/api/v1/logs/download` - raw file download
- [x] 5.8 Register router in `main_local.py`
- [ ] 5.9 Deprecate/remove old `/api/v1/ingestion/logs` endpoint (redirect to unified API)

## 6. WebSocket Log Streaming

- [x] 6.1 Implement `/ws/logs` WebSocket endpoint
- [x] 6.2 Add real-time log sink that broadcasts to WebSocket clients
- [x] 6.3 Implement filtering by category, level, module
- [x] 6.4 Implement filtering by ingestion_id for real-time ingestion monitoring
- [x] 6.5 Add backpressure handling and heartbeat
- [ ] 6.6 Add authentication for WebSocket connection (same JWT as REST)

## 7. OpenTelemetry Integration

- [ ] 7.1 Modify `src/utils/otel.py` to remove log exporter
- [ ] 7.2 Keep trace and metric exporters unchanged
- [ ] 7.3 Add trace_id/span_id injection into Loguru context
- [ ] 7.4 Update SigNoz documentation for trace-log correlation

## 8. File Migration (by module)

- [ ] 8.1 Migrate `src/api/` (routers, middleware) - 12 files
- [ ] 8.2 Migrate `src/services/` - 12 files
- [ ] 8.3 Migrate `src/llm/` - 6 files
- [ ] 8.4 Migrate `src/storage/` - 8 files
- [ ] 8.5 Migrate `src/ingestion/` - 11 files
- [ ] 8.6 Migrate `src/knowledge_graph/` - 2 files
- [ ] 8.7 Migrate `src/utils/` (except audit_logger) - 4 files
- [ ] 8.8 Migrate `src/config/` - 2 files
- [ ] 8.9 Migrate `src/migrations/` - 2 files

## 9. Cleanup & Documentation

- [ ] 9.1 Remove old `src/utils/logging_config.py` after full migration
- [ ] 9.2 Update README with new logging configuration
- [ ] 9.3 Update `.env.example` with new logging env vars
- [ ] 9.4 Verify all tests pass with new logging
- [ ] 9.5 Performance test log throughput

## 10. Frontend Support

- [ ] 10.1 Document unified log API schema (OpenAPI)
- [ ] 10.2 Document WebSocket protocol for real-time logs
- [ ] 10.3 Define frontend log viewer page requirements:
  - Category tabs (All, App, Chat, Audit, Ingestion)
  - Level filter dropdown
  - Time range picker
  - Search box with full-text search
  - Real-time toggle (WebSocket)
  - Log detail panel with JSON view
  - Download button for raw logs
