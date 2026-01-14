# In-Memory DuckDB with Snapshot Management

## Change ID
`inmemory-duckdb-snapshots`

## Problem Statement

The current persistent DuckDB implementation (`data/metadata.duckdb`) experiences file locking issues during container restarts, causing:
- **4-5 failed connection attempts** with "Permission denied" errors
- **4-5 second startup delays** while waiting for file locks to release
- **Unreliable restarts** in containerized environments

### Root Cause
DuckDB's Write-Ahead Log (WAL) maintains file locks that persist briefly after container shutdown. When containers restart quickly (typical in Docker), the new process attempts to open the database file before the old process has fully released the lock.

### Current Workarounds
- Retry mechanism with backoff (already implemented)
- CHECKPOINT before close (attempted but not resolving the issue)

## Proposed Solution

Migrate to **in-memory DuckDB (`:memory:`)** with **automatic snapshot management** to persistent storage. This eliminates file locking entirely while maintaining data persistence through periodic snapshots.

### Key Benefits
1. **Eliminates file locking**: In-memory databases have no file locks
2. **Faster queries**: In-memory operations are significantly faster than disk I/O
3. **Data persistence**: Automatic snapshots ensure data survives restarts
4. **Historical queries**: Load any snapshot to query point-in-time data
5. **Better for containers**: No shared file state between container instances

## User Requirements

### Backend Requirements
1. **In-Memory Operation**: Use `:memory:` as primary DuckDB database
2. **Automatic Snapshots**: 
   - Check for data changes every 5 minutes
   - Create snapshot only if data has changed
   - Store snapshots in `data/snapshots/` directory
   - Keep only 5 most recent snapshots
3. **Snapshot on Shutdown**: Create final snapshot during graceful shutdown
4. **Load on Startup**: Restore latest snapshot into memory on container start

### Frontend Requirements
1. **Snapshot Management UI**: 
   - View list of available snapshots (descending order by timestamp)
   - Select snapshot to query
   - Query live in-memory database
2. **Query Interface**:
   - Execute custom DuckDB SQL commands
   - View query results in table format
   - Support both live and snapshot queries

## Success Criteria

- [ ] Backend starts without DuckDB file locking errors
- [ ] Data persists across container restarts
- [ ] Snapshots created automatically every 5 minutes (if data changed)
- [ ] Only 5 most recent snapshots retained
- [ ] Frontend can list and select snapshots
- [ ] Frontend can execute DuckDB queries against live or snapshot databases
- [ ] Query results displayed in readable format

## Scope

### In Scope
- Migrate DuckDB client to in-memory mode
- Implement snapshot creation/loading logic
- Add background task for periodic snapshots
- Create API endpoints for snapshot management
- Create API endpoint for executing DuckDB queries
- Build frontend UI for snapshot selection and querying
- Update Database page with new functionality

### Out of Scope
- Snapshot compression or encryption
- Snapshot replication to external storage
- Advanced query builder UI (raw SQL only)
- Query result export functionality (can be added later)

## Dependencies

- Existing DuckDB client (`src/storage/duckdb_client.py`)
- Existing Database page in frontend
- FastAPI backend framework
- React frontend with shadcn/ui components

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss between snapshots | Medium | Frequent snapshots (5 min), snapshot on shutdown |
| Increased disk usage | Low | Keep only 5 snapshots, auto-cleanup |
| Snapshot creation blocking queries | Low | Async snapshot creation |
| Migration from existing persistent DB | Medium | One-time migration script to create initial snapshot |

## Open Questions

None - requirements are clear from user feedback.

## Related Changes

- Previous attempt: `fix-duckdb-initialization` (archived) - Implemented retry mechanism
- This change supersedes the file locking workarounds with a architectural solution
