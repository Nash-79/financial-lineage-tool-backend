## Context

The backend currently uses Python's built-in `logging` module across 61 files with varying patterns. `structlog` is installed but unused. OpenTelemetry is configured for traces, metrics, AND logs—but the log export adds complexity without clear benefit since logs end up in files anyway.

**Stakeholders**: Backend developers, DevOps, frontend team (for log viewer)

**Constraints**:
- Must not break existing functionality during migration
- Audit logger must remain unchanged (security-critical)
- OpenTelemetry tracing must continue working
- Logs must be queryable from frontend

## Goals / Non-Goals

### Goals
- Simplify logging with Loguru's cleaner API
- Centralize log access via REST API and WebSocket
- Maintain trace correlation with OpenTelemetry
- Enable real-time log monitoring in frontend
- Reduce logging boilerplate across codebase

### Non-Goals
- Replacing OpenTelemetry tracing (we keep it)
- Changing audit logger implementation
- Building a full log aggregation system (like ELK)
- Supporting external log shipping (Datadog, Splunk) in this change

## Decisions

### Decision 1: Loguru over structlog
**What**: Use Loguru instead of enabling structlog
**Why**:
- Loguru has simpler API (`from loguru import logger`)
- Zero configuration required for basic usage
- Better exception formatting with syntax highlighting
- Easier context binding (`logger.bind()`)
- structlog requires more boilerplate for similar features

**Alternatives considered**:
- Enable structlog: More configuration overhead, less intuitive API
- Keep standard logging: Verbose, requires factory pattern everywhere
- python-json-logger: Only solves JSON formatting, not the API issues

### Decision 2: Logging Intercept for Migration
**What**: Use Loguru's intercept handler to capture standard `logging` calls
**Why**:
- Allows gradual migration without big-bang refactor
- Existing code continues working during transition
- Third-party libraries using `logging` are automatically captured

```python
import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record):
        logger.opt(depth=6, exception=record.exc_info).log(
            record.levelname, record.getMessage()
        )

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

### Decision 3: Keep OpenTelemetry for Tracing Only
**What**: Remove OTLP log export, keep trace and metric export
**Why**:
- Log files are more accessible than OTLP log records
- Reduces OTLP endpoint load
- Simpler debugging (just read the file)
- Trace correlation still works via trace_id in log messages

**Trade-off**: Logs won't appear in SigNoz log viewer, but trace correlation enables jumping from trace to log file.

### Decision 4: Unified Log Storage with Single API
**What**: Consolidate ALL logs under unified structure, expose via single REST API
**Why**:
- Frontend can query all logs from one endpoint (`/api/v1/logs`)
- Consistent JSONL format enables unified parsing
- Single API reduces frontend complexity
- Categories allow filtering without separate endpoints

**Unified file structure**:
```
logs/
├── app/                         # Application logs (Loguru output)
│   ├── app_2024-01-15.jsonl    # Current day
│   ├── app_2024-01-14.jsonl.gz # Compressed previous days
│   └── app_2024-01-13.jsonl.gz
├── chat/                        # Chat interaction logs (migrated to JSONL)
│   ├── chat_2024-01-15.jsonl
│   └── chat_2024-01-14.jsonl.gz
├── audit/                       # Security/compliance audit logs (already JSONL)
│   ├── audit_2024-01-15.jsonl
│   └── audit_2024-01-14.jsonl.gz
└── ingestion/                   # Ingestion session logs
    ├── _index.jsonl             # Index of all sessions (for fast lookup)
    ├── ing_abc123.jsonl         # Per-session detailed logs
    └── ing_def456.jsonl
```

**Unified JSONL schema** (common fields across all categories):
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "category": "app|chat|audit|ingestion",
  "level": "DEBUG|INFO|WARNING|ERROR|CRITICAL",
  "message": "Human readable message",
  "module": "src.services.chat_service",
  "request_id": "req-abc-123",
  "trace_id": "otel-trace-id",
  "extra": { /* category-specific fields */ }
}
```

**Category-specific extra fields**:
- `app`: `function`, `line`, `exception`
- `chat`: `chat_id`, `user_id`, `model`, `latency_ms`, `tokens`
- `audit`: `event_type`, `user_id`, `resource`, `action`, `success`
- `ingestion`: `ingestion_id`, `file_path`, `status`, `nodes_created`

### Decision 5: WebSocket for Real-time Streaming
**What**: Implement `/ws/logs` for live log streaming
**Why**:
- Enables real-time monitoring dashboard
- More efficient than polling REST endpoint
- Supports filtering to reduce bandwidth

**Protocol**:
```json
// Client → Server: Set filter
{"action": "filter", "level": "ERROR", "module": "src.api.*"}

// Server → Client: Log entry
{"timestamp": "...", "level": "ERROR", "module": "...", "message": "..."}

// Server → Client: Heartbeat
{"action": "heartbeat"}

// Server → Client: Dropped notification
{"action": "dropped", "count": 42}
```

## Risks / Trade-offs

### Risk: Migration Breaks Logging
**Mitigation**: Intercept handler ensures old code works. Migrate incrementally with tests.

### Risk: Log File Growth
**Mitigation**: Daily rotation, compression after 1 day, configurable retention (default 30 days).

### Risk: Log API Performance
**Mitigation**:
- Pagination with max 1000 entries
- Index by date (one file per day)
- Full-text search limited to single day by default

### Trade-off: No External Log Aggregation
**Accepted**: This change focuses on local log access. External shipping (Datadog, etc.) can be added later via Loguru sink.

## Migration Plan

### Phase 1: Setup (Non-breaking)
1. Add Loguru dependency
2. Create `loguru_config.py` alongside existing `logging_config.py`
3. Add intercept handler to capture existing logging calls
4. Deploy and verify existing behavior unchanged

### Phase 2: New Features
1. Implement log viewer API (`/api/v1/logs`)
2. Implement WebSocket streaming (`/ws/logs`)
3. Deploy and test with frontend

### Phase 3: Gradual Migration
1. Migrate files by module (services, routers, etc.)
2. Replace `logging.getLogger(__name__)` with `from loguru import logger`
3. Update log calls to use Loguru patterns

### Phase 4: Cleanup
1. Remove intercept handler
2. Delete old `logging_config.py`
3. Remove `structlog` dependency
4. Update documentation

### Rollback
- Revert to previous commit
- Old `logging_config.py` remains until Phase 4
- No database migrations involved

## Open Questions

1. **Log retention policy**: Default 30 days—is this appropriate for compliance?
2. **WebSocket authentication**: Use same JWT as REST API or separate token?
3. **Frontend log viewer scope**: Full implementation or just API documentation for frontend team?

## Appendix: Current vs New Logging Comparison

### Current (Python logging)
```python
import logging

logger = logging.getLogger(__name__)

def process_file(file_path: str):
    logger.info(f"Processing file: {file_path}")
    try:
        result = do_work()
        logger.info(f"Completed processing: {len(result)} items")
    except Exception as e:
        logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
```

### New (Loguru)
```python
from loguru import logger

def process_file(file_path: str):
    logger.info("Processing file: {}", file_path)
    try:
        result = do_work()
        logger.info("Completed processing: {} items", len(result))
    except Exception as e:
        logger.exception("Failed to process {}", file_path)
```

### With Context Binding
```python
from loguru import logger

def process_request(request_id: str, user_id: str):
    with logger.contextualize(request_id=request_id, user_id=user_id):
        logger.info("Starting request")
        # All logs in this block include request_id and user_id
        do_work()
        logger.info("Request completed")
```
