# Frontend-Backend Integration Design

## Overview

This change fixes integration issues between the frontend dashboard and backend API, focusing on real-time communication and endpoint reliability.

## Architecture Decisions

### 1. WebSocket Implementation Pattern

**Decision**: Implement WebSocket endpoint in admin router with broadcast pattern.

**Rationale**:
- Admin router already handles dashboard-related endpoints (`/api/v1/stats`, `/api/v1/activity/recent`)
- Broadcast pattern allows multiple frontend clients to receive updates
- Simple pub/sub model sufficient for current dashboard needs

**Alternatives Considered**:
- **Separate WebSocket router**: Adds unnecessary complexity for single endpoint
- **SSE (Server-Sent Events)**: Unidirectional only, WebSocket allows future two-way communication
- **Polling**: Inefficient for real-time updates

**Trade-offs**:
- ✅ Simple implementation, easy to maintain
- ✅ Built-in FastAPI WebSocket support
- ❌ Limited to single server (no distributed WebSocket without Redis pub/sub)
- ❌ Connections held open consume resources

### 2. Message Format

**Decision**: Use JSON messages with `{type, data, timestamp}` structure.

**Example**:
```json
{
  "type": "stats_update",
  "data": {
    "totalNodes": 45,
    "filesProcessed": 12
  },
  "timestamp": "2025-12-31T20:00:00Z"
}
```

**Message Types**:
- `stats_update`: Periodic dashboard statistics
- `ingestion_complete`: File processing finished
- `query_complete`: Chat query finished
- `error`: System error occurred
- `connection_ack`: Initial connection confirmation

**Rationale**:
- Type field allows frontend to route messages to appropriate handlers
- Timestamp enables event ordering and staleness detection
- Flexible data payload for different event types

### 3. Connection Management

**Decision**: Accept all connections, send periodic updates, handle disconnects gracefully.

**Connection Flow**:
```
1. Frontend: ws://localhost:8000/api/v1/ws/dashboard
2. Backend: Accept connection, send connection_ack
3. Backend: Send stats_update every 5 seconds
4. Frontend: Display real-time stats
5. Backend: Broadcast events as they occur
6. Either: Close connection (graceful cleanup)
```

**Error Handling**:
- Network errors: Log and close connection
- Invalid messages: Log warning, continue connection
- Max connections: Reject with 503 (future enhancement)

### 4. Activity Tracker Fix

**Problem**: Current middleware passes non-callable to activity tracker.

**Root Cause**: Activity tracker expects callback function but receives incorrect type.

**Solution**:
```python
# Before (broken):
state.activity_tracker = some_non_callable_value

# After (fixed):
state.activity_tracker = ActivityTracker(
    persist_callback=async_persist_event  # Proper async callable
)
```

**Verification**: Check middleware setup in `src/api/middleware.py`

### 5. Pydantic Model Fix

**Problem**: Forward references cause schema generation failure.

**Root Cause**: Models use `Dict[str, Any]` in type annotations without proper imports.

**Solution**:
```python
# Before (broken):
from typing import Annotated
response: Annotated[Dict[str, Any], ...]  # Forward ref issue

# After (fixed):
from typing import Any, Dict
response: Dict[str, Any]  # Explicit imports
```

**Verification**: Test OpenAPI schema generation at `/docs`

## Implementation Plan

### Phase 1: WebSocket Endpoint (High Priority)
1. Add WebSocket imports to `admin.py`
2. Create `/ws/dashboard` endpoint with connection handler
3. Implement message broadcasting for stats updates
4. Add connection tracking and cleanup

### Phase 2: Activity Tracker Fix (Medium Priority)
1. Locate activity tracker initialization in middleware
2. Fix callback function signature
3. Add async error handling for persistence
4. Test activity event logging

### Phase 3: Pydantic Model Fix (Medium Priority)
1. Search for forward reference issues in `src/api/models/`
2. Fix import statements and type annotations
3. Test OpenAPI schema generation
4. Verify `/docs` renders without errors

### Phase 4: Integration Testing (All Phases)
1. Test WebSocket connection from simple Python client
2. Verify message format and periodic updates
3. Test chat endpoints with proper model parameter
4. Verify activity events persist correctly

## Security Considerations

**WebSocket Authentication**:
- Current: No authentication (same as other endpoints)
- Future: Add token-based auth if needed

**Rate Limiting**:
- Limit to 10 concurrent WebSocket connections per IP
- Prevent connection spam attacks

**Input Validation**:
- No client→server messages currently (broadcast only)
- Validate message structure before broadcasting

## Testing Strategy

### Unit Tests
- WebSocket connection accept/reject logic
- Message serialization/deserialization
- Connection cleanup on errors

### Integration Tests
- Connect to `/ws/dashboard`, receive `connection_ack`
- Receive periodic `stats_update` messages
- Verify stats match `/api/v1/stats` endpoint
- Test graceful disconnect

### Manual Testing
- Connect from browser console: `new WebSocket('ws://localhost:8000/ws/dashboard')`
- Verify messages in Network tab
- Test connection with frontend dashboard

## Rollout Plan

1. **Development**: Implement and test locally with Docker
2. **Validation**: Run integration tests, verify logs
3. **Frontend Testing**: Coordinate with frontend team for integration
4. **Production**: Deploy with backend update, monitor WebSocket connections

## Monitoring

**Metrics to Track**:
- Active WebSocket connections
- Messages sent per minute
- Connection errors/disconnects
- Activity persistence success/failure rate

**Logging**:
- WebSocket connection/disconnection events
- Activity tracker errors
- Pydantic schema generation warnings
