# Implementation Tasks

## 1. Backend - System Status API

- [x] 1.1 Create `src/api/routers/system.py` with consolidated status endpoint
- [x] 1.2 Add DuckDB pool statistics to health response (connection count, available, max)
- [x] 1.3 Add snapshot info to health response (last snapshot path, timestamp, pending changes flag)
- [x] 1.4 Add model config completeness check to health response
- [x] 1.5 Create `/api/v1/models/availability` endpoint returning per-usage-type status
- [x] 1.6 Create `/api/v1/logs/summary` endpoint returning 24h category stats
- [x] 1.7 Register new router in `main_local.py`
- [x] 1.8 Add Pydantic response models for new endpoints

## 2. Backend - Enhanced Health Endpoint

- [x] 2.1 Extend `HealthResponse` model with optional `duckdb`, `model_configs`, `logs` sections
- [x] 2.2 Implement DuckDB connection pool stats retrieval
- [x] 2.3 Implement OpenRouter quota check (if API available, else mark as "unknown")
- [x] 2.4 Add feature flags to health response (USE_LLAMAINDEX, ENABLE_HYBRID_SEARCH, etc.)
- [x] 2.5 Add backward-compatible response (new fields optional)

## 3. Frontend - Type Definitions

- [x] 3.1 Create `src/types/system.ts` with SystemStatus, ModelAvailability, LogSummary types
- [x] 3.2 Update `src/types/health.ts` with extended health response fields
- [x] 3.3 Add ChatMode enum and availability status types

## 4. Frontend - API Hooks

- [x] 4.1 Create `useSystemStatus()` hook fetching `/api/v1/system/status`
- [x] 4.2 Create `useModelAvailability()` hook fetching `/api/v1/models/availability`
- [x] 4.3 Create `useLogSummary()` hook fetching `/api/v1/logs/summary`
- [x] 4.4 Update `useHealthStatus()` to handle new optional fields
- [x] 4.5 Add appropriate stale times and refetch intervals

## 5. Frontend - Dashboard Widgets

- [x] 5.1 Create `SystemHealthCard` component with expandable service rows
- [x] 5.2 Create `ModelAvailabilityWidget` showing chat mode readiness
- [x] 5.3 Create `LogSummaryWidget` with error badges and category breakdown
- [x] 5.4 Create `ConfigurationStatusCard` showing required vs configured items
- [x] 5.5 Create `DuckDBStatusCard` showing mode, pool, snapshot info (integrated into SystemHealthCard)
- [x] 5.6 Update `ServiceHealthWidget` to use new expanded data (replaced by SystemHealthCard)

## 6. Frontend - Dashboard Page

- [x] 6.1 Redesign `Dashboard.tsx` layout with responsive grid
- [x] 6.2 Add collapsible sections for widget groups (using Tabs)
- [x] 6.3 Add per-widget refresh controls with last-updated timestamps
- [x] 6.4 Implement dark mode styling improvements (inherits from existing theme)
- [x] 6.5 Add loading skeletons for each widget
- [x] 6.6 Add error boundaries per widget (graceful degradation)

## 7. Frontend - Navigation & Integration

- [x] 7.1 Add quick links from dashboard to relevant configuration pages
- [x] 7.2 Add click-through from log summary to log viewer with filters
- [x] 7.3 Add click-through from model availability to model config page
- [x] 7.4 Update Settings page with link to new system status endpoint (via quick actions)

## 8. Testing

- [x] 8.1 Add backend tests for `/api/v1/system/status` endpoint
- [x] 8.2 Add backend tests for `/api/v1/models/availability` endpoint
- [x] 8.3 Add backend tests for `/api/v1/logs/summary` endpoint
- [ ] 8.4 Add backend tests for enhanced health response
- [ ] 8.5 Add frontend component tests for new widgets
- [ ] 8.6 Add integration test for dashboard data flow

## 9. Documentation

- [ ] 9.1 Update API documentation with new endpoints
- [ ] 9.2 Add dashboard widget configuration docs
- [ ] 9.3 Update troubleshooting guide with new status indicators
