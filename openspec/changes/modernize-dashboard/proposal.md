# Change: Modernize Dashboard with Comprehensive System Status

## Why

The current dashboard provides basic statistics (nodes, files, tables, queries) but lacks visibility into critical system components that have been added over time: model configuration status, log viewer integration, DuckDB health, OpenRouter availability, and service-specific metrics. Users cannot quickly assess system readiness or troubleshoot configuration issues without navigating multiple pages or checking logs.

## What Changes

### Backend API Enhancements

1. **New `/api/v1/system/status` endpoint** - Consolidated system status aggregating:
   - Service health (Ollama, Qdrant, Neo4j, Redis, OpenRouter)
   - Database status (DuckDB connection pool, migration state, snapshot info)
   - Model configuration completeness (all usage types configured)
   - Log system status (categories, recent error counts)
   - Feature flags and capabilities

2. **Enhanced `/health` response** - Add:
   - `duckdb.pool_stats` (active connections, available, max)
   - `duckdb.snapshot_info` (last snapshot, pending changes)
   - `openrouter.quota_status` (if API supports it)
   - `model_configs.completeness` (configured/required count)

3. **New `/api/v1/models/availability` endpoint** - Per-usage-type model availability:
   - Which chat modes are fully configured
   - Fallback chain status
   - Provider availability (Ollama online, OpenRouter key valid)

4. **Enhanced `/api/v1/logs/summary` endpoint** - Quick log overview:
   - Per-category counts (last 24h)
   - Error/critical counts
   - Latest error messages (truncated)

### Frontend Dashboard Overhaul

1. **System Health Card (New)** - Replace basic service list with detailed status:
   - Expandable service rows with detailed metrics
   - DuckDB: mode, connection pool, last snapshot
   - OpenRouter: configured, quota status
   - Model configs: X of Y configured with breakdown

2. **Model Availability Widget (New)** - Visual chat mode readiness:
   - Chat modes (deep, semantic, graph, text) with green/yellow/red status
   - Provider status (Ollama, OpenRouter) with connection indicators
   - Quick link to model configuration page

3. **Log Summary Widget (New)** - At-a-glance log health:
   - Error count badges per category
   - Sparkline of log volume (24h)
   - Click to navigate to log viewer with pre-filtered category

4. **Configuration Status Card (New)** - System configuration completeness:
   - Required vs configured items checklist
   - Missing configuration warnings
   - Quick actions to resolve issues

5. **Modernized Layout** - Responsive grid with:
   - Collapsible sections for power users
   - Refresh controls per widget
   - Last-updated timestamps
   - Dark mode support improvements

### **BREAKING** Changes

- `GET /health` response schema adds new optional fields
- Dashboard component props change (existing customizations may need updates)

## Impact

- **Affected specs**: `websocket-dashboard`, `ui-experience`
- **Affected backend code**:
  - `src/api/routers/health.py` - Enhanced health response
  - `src/api/routers/models.py` - New availability endpoint
  - `src/api/routers/logs.py` - New summary endpoint
  - New `src/api/routers/system.py` - Consolidated status endpoint
- **Affected frontend code**:
  - `src/pages/Dashboard.tsx` - Complete rewrite
  - `src/components/dashboard/` - New widgets
  - `src/hooks/useSystemStatus.ts` - New hook
  - `src/hooks/useModelAvailability.ts` - New hook
  - `src/types/system.ts` - New types
