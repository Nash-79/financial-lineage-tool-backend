# Implementation Tasks

## Phase 1: Backend - Snapshot Infrastructure (Backend)

### 1.1 Create Snapshot Manager Module
- [x] Create `data/snapshots/` directory structure
- [x] Create `src/storage/snapshot_manager.py`
- [x] Implement `SnapshotManager` class with:
  - `create_snapshot(db_conn, snapshot_path)` - Export database to data/snapshots/
  - `load_snapshot(snapshot_path)` - Import database from data/snapshots/
  - `list_snapshots()` - Get all snapshots from data/snapshots/ sorted by timestamp
  - `cleanup_old_snapshots(keep_count=5)` - Remove old snapshots
  - `get_latest_snapshot()` - Find most recent snapshot in data/snapshots/
  - `has_data_changed()` - Check if database has changed since last snapshot

**Validation**: Unit tests for all snapshot operations

### 1.2 Update DuckDB Client for In-Memory Mode
- [x] Modify `DuckDBClient.__init__()` to support in-memory mode
- [x] Update `initialize()` to load latest snapshot on startup
- [x] Add `create_snapshot()` method to DuckDBClient
- [x] Add change tracking (track last snapshot hash/timestamp)
- [x] Update `close()` to create final snapshot before shutdown

**Validation**: DuckDB client tests pass, snapshot created on close

### 1.3 Implement Background Snapshot Task
- [x] Create background task in `main_local.py` lifespan
- [x] Check for data changes every 5 minutes
- [x] Create snapshot only if data has changed
- [x] Call `cleanup_old_snapshots()` after each snapshot

**Validation**: Snapshots created automatically, old ones cleaned up

## Phase 2: Backend - API Endpoints

### 2.1 Snapshot Management API
- [x] Create `src/api/routers/snapshots.py`
- [x] `GET /api/v1/snapshots` - List all snapshots with metadata
- [x] `GET /api/v1/snapshots/{snapshot_id}` - Get snapshot details
- [x] Response includes: timestamp, file_size, record_count

**Validation**: API returns snapshot list correctly

### 2.2 DuckDB Query API
- [x] Add `POST /api/v1/database/query` endpoint
- [x] Accept: `{sql: string, snapshot_id?: string}`
- [x] If snapshot_id provided, load snapshot and query it
- [x] If no snapshot_id, query live in-memory database
- [x] Return: `{columns: string[], rows: any[][], row_count: number}`
- [x] Add SQL injection protection and query validation

**Validation**: Can query both live and snapshot databases

## Phase 3: Frontend - Database Page UI

### 3.1 Snapshot Selector Component
- [x] Create `src/components/database/SnapshotSelector.tsx`
- [x] Fetch snapshots from API
- [x] Display in dropdown/select (descending order by timestamp)
- [x] Include "Live Database" option
- [x] Show snapshot metadata (timestamp, size)

**Validation**: Snapshots load and can be selected

### 3.2 Query Interface Component
- [x] Create `src/components/database/QueryInterface.tsx`
- [x] SQL input textarea with syntax highlighting (optional)
- [x] Execute button
- [x] Results table component
- [x] Error display for invalid queries
- [x] Loading state during query execution

**Validation**: Can execute queries and see results

### 3.3 Integrate into Database Page
- [x] Update `src/pages/Database.tsx`
- [x] Add SnapshotSelector component
- [x] Add QueryInterface component
- [x] Wire up snapshot selection to query execution
- [x] Add helpful examples/documentation

**Validation**: Full workflow works end-to-end

## Phase 4: Migration & Testing

### 4.1 Data Migration
- [x] Create migration script to convert existing `metadata.duckdb` to snapshot
- [x] Add environment variable `DUCKDB_MODE` (memory|persistent) for gradual rollout
- [ ] Update documentation

**Validation**: Existing data migrated successfully (automatic via snapshot loading)

### 4.2 Integration Testing
- [x] Test backend restart with snapshot restoration
- [x] Test snapshot creation on data changes (event-driven working!)
- [x] Test snapshot cleanup (keeps only 5)
- [ ] Test frontend query execution
- [ ] Test snapshot selection and querying

**Validation**: All integration tests pass

### 4.3 Documentation Review and Updates
- [ ] Review and update `README.md` with new DuckDB architecture
- [ ] Update `CONTRIBUTING.md` if development setup changed
- [ ] Review `docs/` directory for DuckDB-related documentation
- [ ] Update API documentation for new snapshot endpoints
- [ ] Update deployment guides with snapshot directory requirements
- [ ] Add snapshot management documentation
- [ ] Add query interface usage examples
- [ ] Update environment variable documentation (`DUCKDB_MODE`)
- [ ] Review and update any architecture diagrams
- [ ] Update troubleshooting guides (remove file locking issues)

**Validation**: All documentation accurately reflects new architecture

---

## ✅ BACKEND IMPLEMENTATION COMPLETE

**What's Working:**
- ✅ In-memory DuckDB (no file locking!)
- ✅ Event-driven snapshots (triggers on write)
- ✅ Automatic snapshot loading on restart
- ✅ Snapshot retention (keeps 5 most recent)
- ✅ Enhanced logging with completion messages
- ✅ GET /api/v1/snapshots API
- ✅ POST /api/v1/database/query API

**Next Phase:** Frontend UI (Phase 3) or Documentation (Phase 4.3)

## Dependencies

- Phase 2 depends on Phase 1 completion
- Phase 3 depends on Phase 2.2 completion
- Phase 4 depends on all previous phases

## Estimated Effort

- Phase 1: 4-6 hours
- Phase 2: 2-3 hours
- Phase 3: 3-4 hours
- Phase 4: 3-4 hours (includes comprehensive documentation review)
- **Total**: 12-17 hours
