# Database Schema Migration Changelog

This document tracks all DuckDB schema migrations applied to the system.

## Migration History

### Version 6 (2026-01-13)
**OpenSpec Change**: enhance-zero-cost-hybrid-lineage

**Changes**:
- Rebuilt `files` table without PRIMARY KEY (uses UNIQUE index on `id`)
- Added `project_links` table for cross-project relationships
- Refreshed file macros with repository-aware signatures
  - `find_duplicate_file(proj_id, repo_id, rel_path, fhash)`
  - `find_previous_file_version(proj_id, repo_id, rel_path)`

**Affected Features**:
- File status updates (DuckDB constraint fix)
- Project-to-project linking
- File deduplication macros

**Risk**: Medium (table rebuild + data copy)

---

### Version 5 (2026-01-09)
**OpenSpec Change**: align-frontend-backend-api

**Changes**:
- Added file metadata columns: `relative_path`, `file_type`, `source`, `repository_id`, `status`
- Added indexes for file filtering and status queries
- Updated file deduplication macros to be repository-aware

**Affected Features**:
- File listing and filtering
- Repository-scoped deduplication

**Risk**: Low (additive columns)

---

### Version 4 (2026-01-03)
**OpenSpec Change**: persist-upload-settings

**Changes**:
- Added `upload_settings` table for persistent file upload configuration
- Single-row table with id='default'
- Stores allowed_extensions (JSON), max_file_size_mb, updated_at, updated_by

**Affected Features**:
- `PUT /api/v1/files/config` - now persists to database
- `GET /api/v1/files/config` - loads from database
- Settings survive server restarts

**Risk**: Low (new table, no data migration)

---

### Version 3 (2026-01-02)
**OpenSpec Change**: structure-data-outputs

**Changes**:
- Added `runs` table for ingestion run tracking
- Added `files` table for file version management
- Added 5 indexes for performance:
  - `idx_runs_project_timestamp`
  - `idx_files_project_filename`
  - `idx_files_hash`
  - `idx_files_project_hash`
  - `idx_files_run`
- Added 3 DuckDB macros for business logic:
  - `get_next_sequence(proj_id, ts)` - Get next sequence number
  - `find_duplicate_file(proj_id, repo_id, rel_path, fhash)` - Find duplicates by hash
  - `find_previous_file_version(proj_id, repo_id, rel_path)` - Find previous versions

**Affected Features**:
- File upload with content hashing
- File deduplication
- File versioning and superseding
- Artifact management

**Risk**: Medium (complex schema with foreign keys)

---

### Version 2 (2026-01-02)
**OpenSpec Change**: add-user-prompt-context

**Changes**:
- Added `context` column to projects table (JSON)
- Added `context_file_path` column to projects table (VARCHAR)

**Affected Features**:
- `GET /api/v1/projects/{project_id}/context`
- `PUT /api/v1/projects/{project_id}/context`
- `POST /api/v1/projects/{project_id}/context/upload`

**Risk**: Low (additive columns)

---

### Version 1 (Initial)
**OpenSpec Change**: Initial schema

**Changes**:
- Created `projects` table
- Created `repositories` table
- Created `links` table
- Created `schema_version` table

**Affected Features**: Core project management

**Risk**: N/A (initial creation)

---

## Checking Migration Status

### Via Health Endpoint
```bash
curl http://localhost:8000/health | jq '.database'
```

Expected response:
```json
{
  "schema_version": 6,
  "is_current": true,
  "total_migrations": 6,
  "last_migration": "2026-01-13T12:00:00"
}
```

### Via Python
```python
from src.storage.duckdb_client import get_duckdb_client

db = get_duckdb_client()
status = db.get_migration_status()
print(f"Current version: {status['current_version']}")
print(f"Is current: {status['is_current']}")
```

### Via Docker Logs
```bash
docker logs lineage-api | grep -A10 "DATABASE SCHEMA MIGRATION"
```

Expected output:
```
======================================================================
DATABASE SCHEMA MIGRATION CHECK
Current version: 6
Target version: 6
Schema is up-to-date
======================================================================
```

---

## Migration Guidelines

### When Adding New Migrations

1. **Increment version number** in `_create_schema()` method
2. **Add new migration method** following naming pattern `_migrate_to_vX()`
3. **Update `latest_version`** in `get_migration_status()` method
4. **Add detailed docstring** with WHAT/WHY/WHEN/CHANGES format
5. **Update this changelog** with new migration details
6. **Test migration** on fresh database and existing database
7. **Ensure idempotency** using `IF NOT EXISTS` clauses

### Migration Best Practices

- ✅ Use `IF NOT EXISTS` for all DDL statements
- ✅ Make migrations additive when possible (avoid DROP/ALTER)
- ✅ Document affected features and API endpoints
- ✅ Include risk assessment in changelog
- ✅ Test rollback scenarios if applicable
- ✅ Log migration progress clearly
- ❌ Avoid destructive changes without backup strategy
- ❌ Don't modify existing data without migration script

---

## Troubleshooting

### Migration Failed During Startup

Check Docker logs:
```bash
docker logs lineage-api 2>&1 | grep -i "migration\|error"
```

### Schema Version Mismatch

Query current version:
```python
from src.storage.duckdb_client import get_duckdb_client
db = get_duckdb_client()
result = db.conn.execute("SELECT version, applied_at FROM schema_version ORDER BY version").fetchall()
print(result)
```

### Reset Database (Development Only)

**WARNING**: This will delete all data!

```bash
docker exec lineage-api rm /app/data/metadata.duckdb
docker restart lineage-api
```

---

## Related Documentation

- [DuckDB Client Implementation](../../src/storage/duckdb_client.py)
- [OpenSpec Changes](../../openspec/changes/)
- [Health Endpoint Documentation](../../src/api/routers/health.py)
