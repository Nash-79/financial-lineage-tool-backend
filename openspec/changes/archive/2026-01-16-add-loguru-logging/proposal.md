# Change: Add Loguru Logging with Centralized Frontend Viewer

## Why

The current logging setup uses Python's built-in `logging` module across 61 files with inconsistent patterns. While `structlog` is installed, it's not actively used. The system lacks a centralized way to view logs from the frontend, making debugging and monitoring cumbersome. Loguru provides simpler syntax, better defaults, automatic formatting, and easier integration while maintaining OpenTelemetry for distributed tracing.

## What Changes

### Logging Framework
- **REPLACE**: Python `logging` module → Loguru for all application logging
- **KEEP**: OpenTelemetry for distributed tracing (traces only, not logging)
- **REMOVE**: Unused `structlog` dependency
- **KEEP**: Audit logger (`src/utils/audit_logger.py`) - security-critical, append-only JSONL

### New Capabilities
- **ADD**: Centralized log viewer API endpoint (`/api/v1/logs`)
- **ADD**: WebSocket real-time log streaming (`/ws/logs`)
- **ADD**: Log filtering by level, module, time range, request ID
- **ADD**: Log search with full-text capabilities
- **ADD**: Frontend log viewer page (backend API support)

### Configuration
- **MODIFY**: `LOG_FORMAT` supports `json` (production) and `pretty` (development)
- **ADD**: `LOG_RETENTION_DAYS` for automatic log rotation/cleanup
- **ADD**: `LOG_SINK` for output destination (file, stdout, both)

### OpenTelemetry Clarification
- OpenTelemetry remains for **tracing** (distributed request tracing across services)
- Loguru handles **logging** (application logs, debug info, errors)
- Both can coexist: Loguru logs can include trace IDs for correlation

## Impact

### Affected Specs
- `specs/logging/spec.md` - Major modifications to logging requirements

### Affected Code
- `src/utils/logging_config.py` - Complete rewrite for Loguru
- `src/utils/otel.py` - Remove log export, keep trace/metric export
- 61 files with `import logging` - Migrate to Loguru
- `src/api/routers/` - New logs router
- `src/api/main_local.py` - Loguru initialization

### Migration Strategy
1. Add Loguru alongside existing logging (non-breaking)
2. Create compatibility shim for gradual migration
3. Migrate files incrementally by module
4. Remove old logging after full migration

### Breaking Changes
- None for external APIs
- Internal: `logging.getLogger()` calls must be migrated
