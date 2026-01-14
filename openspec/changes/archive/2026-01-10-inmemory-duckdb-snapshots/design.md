# Design: In-Memory DuckDB with Snapshot Management

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────────────┐     │
│  │  DuckDBClient    │         │  SnapshotManager         │     │
│  │  (:memory:)      │◄────────│  - create_snapshot()     │     │
│  │                  │         │  - load_snapshot()       │     │
│  │  - Projects      │         │  - list_snapshots()      │     │
│  │  - Repositories  │         │  - cleanup_old()         │     │
│  │  - Files         │         │  - has_changed()         │     │
│  │  - Runs          │         └──────────────────────────┘     │
│  └──────────────────┘                     │                     │
│         ▲                                 │                     │
│         │ Load on startup                 ▼                     │
│         │                     ┌──────────────────────────┐     │
│         └─────────────────────│  Disk Snapshots          │     │
│                               │  /app/data/snapshots/    │     │
│                               │  - snapshot_*.duckdb     │     │
│                               │  (keep 5 most recent)    │     │
│                               └──────────────────────────┘     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Background Task (asyncio)                           │      │
│  │  - Every 5 minutes: check if data changed            │      │
│  │  - If changed: create snapshot + cleanup old         │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  API Endpoints                                       │      │
│  │  GET  /api/v1/snapshots                              │      │
│  │  POST /api/v1/database/query                         │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     React Frontend                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Database Page                                       │      │
│  │                                                      │      │
│  │  ┌────────────────────────────────────────┐         │      │
│  │  │  Snapshot Selector                     │         │      │
│  │  │  ┌──────────────────────────────────┐  │         │      │
│  │  │  │ ● Live Database (In-Memory)      │  │         │      │
│  │  │  │   Snapshot 2026-01-09 21:20:15   │  │         │      │
│  │  │  │   Snapshot 2026-01-09 21:15:10   │  │         │      │
│  │  │  │   Snapshot 2026-01-09 21:10:05   │  │         │      │
│  │  │  └──────────────────────────────────┘  │         │      │
│  │  └────────────────────────────────────────┘         │      │
│  │                                                      │      │
│  │  ┌────────────────────────────────────────┐         │      │
│  │  │  Query Interface                       │         │      │
│  │  │  ┌──────────────────────────────────┐  │         │      │
│  │  │  │ SELECT * FROM projects;          │  │         │      │
│  │  │  │                                  │  │         │      │
│  │  │  └──────────────────────────────────┘  │         │      │
│  │  │  [Execute Query]                       │         │      │
│  │  │                                        │         │      │
│  │  │  Results:                              │         │      │
│  │  │  ┌──────────────────────────────────┐  │         │      │
│  │  │  │ id    │ name         │ created  │  │         │      │
│  │  │  │ proj1 │ My Project   │ 2026...  │  │         │      │
│  │  │  └──────────────────────────────────┘  │         │      │
│  │  └────────────────────────────────────────┘         │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Snapshot Format: DuckDB Native Export

**Decision**: Use DuckDB's `EXPORT DATABASE` command for snapshots

**Rationale**:
- Native DuckDB format ensures perfect schema/data fidelity
- ACID-compliant snapshots
- Fast export/import operations
- No custom serialization logic needed

**Alternative Considered**: Parquet files
- **Rejected**: More complex, requires schema management, slower

### 2. Snapshot Naming Convention

**Format**: `data/snapshots/snapshot_YYYYMMDD_HHMMSS.duckdb`

**Example**: `data/snapshots/snapshot_20260109_212015.duckdb`

**Rationale**:
- Sortable by filename (descending order)
- Human-readable timestamp
- No timezone ambiguity (use UTC)
- Easy to parse programmatically

### 3. Change Detection Strategy

**Approach**: Track last snapshot timestamp + row count hash

```python
def has_data_changed(self) -> bool:
    current_hash = self._compute_data_hash()
    return current_hash != self._last_snapshot_hash
    
def _compute_data_hash(self) -> str:
    # Simple approach: count rows in all tables
    counts = {}
    for table in ['projects', 'repositories', 'files', 'runs']:
        count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts[table] = count
    return hashlib.md5(json.dumps(counts).encode()).hexdigest()
```

**Rationale**:
- Lightweight check (no full table scans)
- Detects additions/deletions
- Fast execution (< 10ms)

**Trade-off**: Won't detect updates to existing rows (acceptable for this use case)

### 4. Snapshot Retention Policy

**Policy**: Keep only 5 most recent snapshots

**Cleanup Logic**:
```python
def cleanup_old_snapshots(self, keep_count: int = 5):
    snapshots = sorted(self.list_snapshots(), key=lambda s: s['timestamp'], reverse=True)
    to_delete = snapshots[keep_count:]
    for snapshot in to_delete:
        os.remove(snapshot['path'])
```

**Rationale**:
- Balances disk usage with historical access
- 5 snapshots @ 5-min intervals = 25 minutes of history
- User can adjust via environment variable if needed

### 5. Query Execution Model

**Live Database**:
```python
# Direct query on in-memory database
result = duckdb_client.execute(sql)
```

**Snapshot Database**:
```python
# Create temporary connection to snapshot in data/snapshots/
snapshot_path = f"data/snapshots/snapshot_{snapshot_id}.duckdb"
snapshot_conn = duckdb.connect(snapshot_path, read_only=True)
result = snapshot_conn.execute(sql)
snapshot_conn.close()
```

**Rationale**:
- Read-only snapshot connections prevent accidental modifications
- Temporary connections don't interfere with live database
- Simple and safe

### 6. Background Task Implementation

**Approach**: AsyncIO periodic task in FastAPI lifespan

```python
async def snapshot_task():
    while True:
        await asyncio.sleep(300)  # 5 minutes
        if snapshot_manager.has_data_changed():
            snapshot_manager.create_snapshot()
            snapshot_manager.cleanup_old_snapshots()
```

**Rationale**:
- Non-blocking (doesn't interfere with API requests)
- Graceful shutdown support
- Simple to implement and maintain

## Data Flow

### Startup Flow
```
1. Container starts
2. DuckDBClient initializes with :memory:
3. SnapshotManager checks for latest snapshot
4. If snapshot exists:
   - Load snapshot into :memory: database
5. If no snapshot:
   - Start with empty database
6. Start background snapshot task
7. Application ready
```

### Snapshot Creation Flow
```
1. Background task wakes up (every 5 min)
2. Check if data has changed
3. If changed:
   a. Generate snapshot filename with current timestamp
   b. Execute: EXPORT DATABASE 'path/to/snapshot'
   c. Update last_snapshot_hash
   d. Cleanup old snapshots (keep 5)
4. If not changed:
   - Skip snapshot creation
```

### Query Flow
```
1. Frontend sends POST /api/v1/database/query
   {sql: "SELECT * FROM projects", snapshot_id: "20260109_212015"}
2. Backend validates SQL
3. If snapshot_id:
   a. Construct path: data/snapshots/snapshot_{snapshot_id}.duckdb
   b. Load snapshot connection (read-only)
   c. Execute query on snapshot
   d. Close snapshot connection
4. If no snapshot_id:
   a. Execute query on live :memory: database
5. Return results: {columns, rows, row_count}
```

## Security Considerations

### SQL Injection Protection
- Validate SQL syntax before execution
- Whitelist allowed SQL commands (SELECT only, no DDL/DML)
- Use DuckDB's parameter binding where possible
- Limit query execution time (timeout)

### Access Control
- Queries are read-only (no INSERT/UPDATE/DELETE)
- Snapshot connections opened in read-only mode
- No file system access from SQL queries

## Performance Considerations

### Memory Usage
- In-memory database size: ~10-50 MB (estimated for typical usage)
- Snapshot size: Same as in-memory size
- Total disk usage: 5 snapshots × 50 MB = 250 MB max

### Query Performance
- In-memory queries: < 10ms for typical queries
- Snapshot queries: < 50ms (includes file load time)
- Snapshot creation: ~100-500ms (non-blocking)

## Error Handling

### Snapshot Creation Failures
- Log error but don't crash application
- Retry on next interval
- Alert if multiple consecutive failures

### Snapshot Load Failures
- Fall back to empty database
- Log warning
- Continue application startup

### Query Execution Errors
- Return error message to frontend
- Don't expose internal database structure
- Log for debugging

## Testing Strategy

### Unit Tests
- SnapshotManager: All methods tested independently
- DuckDBClient: In-memory mode initialization
- Change detection logic

### Integration Tests
- Full snapshot lifecycle (create, load, cleanup)
- Background task execution
- API endpoint responses

### End-to-End Tests
- Frontend → Backend → Database query flow
- Snapshot selection and querying
- Data persistence across restarts

## Rollback Plan

If issues arise, rollback is simple:
1. Set `DUCKDB_MODE=persistent` in environment
2. Restart container
3. System reverts to file-based DuckDB

Existing snapshots remain available for manual inspection.
