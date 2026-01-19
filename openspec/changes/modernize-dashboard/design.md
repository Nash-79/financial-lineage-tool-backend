# Design: Dashboard Modernization

## Context

The Financial Lineage Tool has evolved significantly with new capabilities:
- DuckDB for metadata storage (in-memory with snapshots)
- OpenRouter integration for cloud LLM access
- Model configuration service for multi-provider routing
- Loguru-based unified logging system
- Multiple chat modes (deep, semantic, graph, text)

The current dashboard shows basic counts but lacks visibility into these systems. Users cannot quickly determine if their system is properly configured and operational.

**Stakeholders**: Developers, operators, end users configuring the system

**Constraints**:
- Must remain performant (dashboard should load in <2s)
- Backend changes must be backward compatible
- Frontend must gracefully degrade if new endpoints unavailable

## Goals / Non-Goals

### Goals
- Single-page visibility into all critical system components
- Clear indication of what's working vs what needs attention
- Quick navigation to resolve configuration issues
- Support both minimal (development) and full (production) deployments

### Non-Goals
- Real-time metrics streaming (existing WebSocket sufficient)
- Historical trend analysis (use external observability tools)
- Automated remediation (dashboard is read-only status)
- Mobile-first design (desktop focus, responsive secondary)

## Decisions

### Decision 1: Consolidated System Status Endpoint

**What**: Create `/api/v1/system/status` that aggregates status from multiple sources.

**Why**: Reduces frontend API calls from 5+ to 1 for initial dashboard load. Provides atomic snapshot of system state.

**Alternatives considered**:
- Keep separate endpoints: More flexible but slower load, harder to show "overall" status
- GraphQL: Overkill for this use case, adds complexity

**Structure**:
```python
class SystemStatus(BaseModel):
    timestamp: datetime
    overall_status: Literal["healthy", "degraded", "unhealthy"]
    services: dict[str, ServiceStatus]  # ollama, qdrant, neo4j, redis, openrouter
    database: DatabaseStatus  # duckdb mode, pool, snapshots
    models: ModelConfigStatus  # completeness, per-usage availability
    logs: LogSummaryStatus  # 24h counts, error count
    features: dict[str, bool]  # feature flags
```

### Decision 2: Model Availability as Separate Concern

**What**: Create `/api/v1/models/availability` returning per-chat-mode readiness.

**Why**: Model configuration is complex (providers, fallbacks, usage types). Dedicated endpoint allows frontend to show actionable status per chat mode.

**Response structure**:
```python
class ModelAvailability(BaseModel):
    chat_modes: dict[str, ChatModeStatus]  # deep, semantic, graph, text
    providers: dict[str, ProviderStatus]  # ollama, openrouter
    configured_usage_types: list[str]
    missing_usage_types: list[str]
```

### Decision 3: Widget-Based Dashboard Architecture

**What**: Dashboard composed of independent widgets, each with own data source and error boundary.

**Why**:
- Graceful degradation (one failing API doesn't break entire dashboard)
- Easier to add/remove widgets
- Consistent UX pattern

**Widget contract**:
```typescript
interface DashboardWidget {
  title: string;
  refreshInterval?: number;
  collapsible?: boolean;
  isLoading: boolean;
  error?: Error;
  onRefresh: () => void;
  lastUpdated?: Date;
}
```

### Decision 4: Extend Health Endpoint (Not Replace)

**What**: Add optional fields to existing `/health` response rather than creating new endpoint.

**Why**: Existing integrations (Docker health checks, monitoring) continue to work. New fields are additive.

**New optional fields**:
```python
class HealthResponse(BaseModel):
    # Existing fields...
    status: str
    services: dict
    rag_mode: str

    # New optional fields
    duckdb: Optional[DuckDBHealth] = None
    model_configs: Optional[ModelConfigHealth] = None
    features: Optional[dict[str, bool]] = None
```

### Decision 5: Log Summary Endpoint

**What**: Create `/api/v1/logs/summary` returning aggregated counts, not individual entries.

**Why**: Dashboard needs counts and error indicators, not full log content. Keeps response small and fast.

**Structure**:
```python
class LogSummary(BaseModel):
    period_hours: int = 24
    categories: dict[str, CategorySummary]
    total_entries: int
    total_errors: int
    latest_error: Optional[LogEntry]  # Most recent error for quick visibility
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| System status endpoint becomes slow | Cache with 10s TTL, async service checks |
| Breaking existing dashboard users | Feature flag for new layout, gradual rollout |
| Too many API calls on page load | Consolidated endpoint reduces calls; stale-while-revalidate |
| DuckDB pool stats not available | Check if pool exists, return nulls gracefully |
| OpenRouter quota API unavailable | Mark as "unknown", don't fail health check |

## Migration Plan

### Phase 1: Backend Endpoints
1. Add new endpoints with feature flag
2. Extend health response with optional fields
3. Deploy backend, verify existing integrations work

### Phase 2: Frontend Widgets
1. Create new widget components
2. Add new hooks with fallback behavior
3. Test with backend feature flag on/off

### Phase 3: Dashboard Redesign
1. Deploy redesigned dashboard behind feature flag
2. A/B test with subset of users
3. Gather feedback, iterate
4. Remove feature flag, deprecate old layout

### Rollback
- Backend: Remove optional fields from health response
- Frontend: Revert to previous Dashboard.tsx commit
- Feature flags allow instant rollback without deployment

## Open Questions

1. **OpenRouter quota API**: Does OpenRouter expose usage/quota endpoints? Need to verify API capabilities.

2. **DuckDB connection pooling**: Current implementation may not use a pool. Verify architecture before implementing pool stats.

3. **Log retention for summary**: Should summary count all logs or respect retention window? Proposal: count files present, not time-based.

4. **Refresh intervals**: What's optimal balance between freshness and API load?
   - System status: 30s
   - Model availability: 60s (rarely changes)
   - Log summary: 60s
   - Health: 30s (existing)
