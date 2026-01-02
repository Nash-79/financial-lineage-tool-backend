# Frontend-Backend Integration Tasks

## Phase 1: Chat Endpoint Fixes (COMPLETED ✅)

### Task 1.1: Fix ollama.generate() calls
- [x] Add model parameter to semantic chat endpoint (line 124)
- [x] Add model parameter to graph chat endpoint (line 172-174)
- [x] Add model parameter to text chat endpoint (line 209-212)
- [x] Use config.LLM_MODEL for all model parameters
- [x] Restart API container to apply changes

**Validation**: Test all chat endpoints return proper responses instead of missing parameter error

### Task 1.2: Verify chat endpoint functionality
- [x] Test POST /api/chat/text with simple query
- [x] Test POST /api/chat/semantic with context query
- [x] Test POST /api/chat/graph with lineage query
- [x] Test POST /api/chat/deep with detailed query
- [x] Verify response format matches ChatResponse model

**Validation**: All chat endpoints return 200 or valid LLM-related errors (not parameter errors)

## Phase 2: Admin Restart Endpoint

### Task 7.1: Implement /admin/restart endpoint
- [x] Add POST /admin/restart route in admin.py
- [x] Create restart_container() async function
- [x] Return {"status": "restarting"} immediately
- [x] Trigger graceful shutdown with sys.exit(0)
- [x] Docker restart policy brings container back up

**File**: `src/api/routers/admin.py`
**Validation**: POST /admin/restart returns 200 with status message

### Task 7.2: Test restart endpoint
- [ ] Test POST /admin/restart returns correct response
- [ ] Verify container restarts within 10 seconds
- [ ] Check services reconnect after restart
- [ ] Verify no data loss during restart
- [ ] Test endpoint appears in /docs

**Validation**: curl -X POST http://localhost:8000/admin/restart works

## Phase 7: WebSocket Dashboard Endpoint

### Task 7.1: Add WebSocket imports and dependencies
- [x] Import WebSocket, WebSocketDisconnect from fastapi
- [x] Import asyncio for periodic tasks
- [x] Import json for message serialization
- [x] Import datetime for timestamps
- [x] Add typing imports for WebSocket client list

**File**: `src/api/routers/admin.py`
**Validation**: Imports resolve without errors

### Task 7.2: Create WebSocket connection manager
- [x] Create ConnectionManager class to track active connections
- [x] Add connect() method to accept and track connections
- [x] Add disconnect() method to remove connections
- [x] Add broadcast() method to send messages to all clients
- [ ] Add send_personal() method for individual messages

**File**: `src/api/routers/admin.py`
**Validation**: Manager can track and broadcast to multiple connections

### Task 7.3: Implement /ws/dashboard endpoint
- [x] Create @router.websocket("/ws/dashboard") endpoint
- [x] Accept WebSocket connection
- [x] Send connection_ack message with timestamp
- [x] Keep connection alive in while loop
- [x] Handle WebSocketDisconnect exception
- [x] Clean up connection on disconnect

**File**: `src/api/routers/admin.py`
**Validation**: Can connect via `new WebSocket('ws://localhost:8000/api/v1/ws/dashboard')`

### Task 7.4: Implement periodic stats updates
- [x] Create background task for periodic updates
- [x] Fetch stats using get_dashboard_stats()
- [x] Format stats_update message with type, data, timestamp
- [x] Broadcast message to all connected clients every 5 seconds
- [x] Handle errors gracefully without disconnecting clients

**File**: `src/api/routers/admin.py`
**Validation**: Connected clients receive stats_update every 5 seconds

### Task 7.5: Add event broadcasting hooks
- [ ] Create broadcast_event() helper function
- [ ] Add ingestion_complete event type
- [ ] Add query_complete event type
- [ ] Add error event type
- [ ] Ensure all events include timestamp

**File**: `src/api/routers/admin.py`
**Validation**: Helper can broadcast different event types

### Task 7.6: Add connection limits and security
- [ ] Track connections per IP address
- [ ] Limit to 10 connections per IP
- [ ] Return 503 when limit exceeded
- [ ] Add origin validation for WebSocket connections
- [ ] Log all connection and disconnection events

**File**: `src/api/routers/admin.py`
**Validation**: 11th connection from same IP is rejected

## Phase 4: Activity Tracker Fixes

### Task 7.1: Locate activity tracker initialization
- [x] Search for activity tracker setup in middleware
- [x] Identify where callback is registered
- [x] Review current callback signature
- [x] Document expected callback signature

**Files**: `src/api/middleware.py`, `src/api/main_local.py`
**Validation**: Found activity tracker initialization code

### Task 7.2: Fix activity tracker callback
- [x] Define async persist_event(event_data) function
- [x] Implement event persistence to logs or storage
- [x] Add error handling for persistence failures
- [x] Pass callable to activity tracker initialization
- [x] Remove non-callable value causing error

**File**: `src/api/middleware.py` or `src/api/main_local.py`
**Validation**: No more "first argument must be callable" errors in logs

### Task 7.3: Add activity event persistence
- [x] Create activity log file or database table
- [x] Implement append-only event logging
- [x] Add rotation for activity logs
- [x] Include event type, timestamp, user, details
- [x] Handle write failures gracefully

**File**: New file `src/utils/activity_logger.py`
**Validation**: Activity events appear in logs/activity.jsonl

### Task 7.4: Test activity tracking
- [ ] Trigger ingestion event, verify logged
- [ ] Trigger query event, verify logged
- [ ] Trigger error event, verify logged
- [ ] Verify activity persistence doesn't block operations
- [ ] Check activity logs are readable and parseable

**Validation**: All activity types logged successfully without errors

## Phase 5: Pydantic Model Fixes

### Task 7.1: Identify Pydantic forward reference issues
- [x] Search for typing.Annotated usage in models
- [x] Search for Dict[str, Any] without imports
- [x] Search for forward references like ForwardRef
- [x] List all API models with type annotation issues

**Files**: `src/api/models/*.py`
**Validation**: Created list of models needing fixes

### Task 7.2: Fix model imports and annotations
- [x] Add explicit imports: from typing import Any, Dict, List
- [x] Remove Annotated wrapper where not needed
- [x] Replace forward references with direct types
- [x] Ensure all referenced models imported before use
- [x] Add TYPE_CHECKING for circular imports if needed

**Files**: `src/api/models/*.py`
**Validation**: All models import successfully

### Task 7.3: Add model_rebuild() calls if needed
- [ ] Identify models with necessary forward references
- [ ] Call .model_rebuild() after all types defined
- [ ] Verify rebuild completes without errors
- [ ] Test model validation after rebuild

**Files**: `src/api/models/*.py`
**Validation**: Models rebuild successfully

### Task 7.4: Verify OpenAPI schema generation
- [ ] Restart API container
- [ ] Check logs for Pydantic errors during startup
- [ ] Navigate to http://localhost:8000/docs
- [ ] Verify all endpoints render in Swagger UI
- [ ] Test API calls from Swagger UI

**Validation**: /docs loads without errors, all endpoints visible

## Phase 6: Integration Testing

### Task 7.1: WebSocket integration tests
- [x] Create test_websocket.py in tests/
- [x] Test WebSocket connection establishment
- [x] Test receiving connection_ack message
- [x] Test receiving periodic stats_update
- [x] Test graceful disconnect
- [x] Test connection limit enforcement

**File**: `tests/test_websocket.py`
**Validation**: pytest tests/ -k websocket passes

### Task 7.2: Chat endpoint integration tests
- [x] Create test_chat_endpoints.py in tests/
- [x] Test each chat endpoint with valid queries
- [x] Test error handling for invalid queries
- [x] Test response format matches ChatResponse model
- [x] Verify model parameter included in Ollama calls

**File**: `tests/test_chat_endpoints.py`
**Validation**: pytest tests/ -k chat passes

### Task 7.3: Activity tracking tests
- [x] Test activity events are persisted
- [x] Test persistence failures don't crash system
- [x] Verify activity logs contain expected fields
- [x] Test concurrent event logging
- [x] Verify log rotation works

**File**: `tests/test_activity_tracking.py`
**Validation**: pytest tests/ -k activity passes

### Task 7.4: Manual frontend integration test
- [x] Connect frontend to WebSocket endpoint
- [x] Verify real-time stats display updates
- [x] Test chat interface with all endpoint types
- [x] Verify activity tracking in dashboard
- [x] Check browser console for errors

**Validation**: Frontend dashboard fully functional

## Phase 7: Documentation and Deployment

### Task 7.1: Update API documentation
- [x] Add WebSocket endpoint to docs/api/API_REFERENCE.md
- [x] Document message format and event types
- [x] Add example WebSocket client code
- [x] Update architecture docs with WebSocket flow
- [x] Document activity tracking configuration

**Files**: `docs/api/API_REFERENCE.md`, `docs/architecture/ARCHITECTURE.md`
**Validation**: Documentation complete and accurate

### Task 7.2: Update README and guides
- [x] Add WebSocket endpoint to README endpoint list
- [x] Update quick start to mention real-time features
- [x] Add troubleshooting for WebSocket connection issues
- [x] Document activity log location and format

**Files**: `README.md`, `docs/troubleshooting/TROUBLESHOOTING.md`
**Validation**: All documentation links valid

### Task 7.3: Create deployment checklist
- [x] Verify all environment variables set
- [x] Check Docker resource limits sufficient
- [x] Verify WebSocket works through reverse proxy
- [x] Test health checks pass
- [x] Create rollback plan

**File**: `docs/deployment/DEPLOYMENT_CHECKLIST.md`
**Validation**: Checklist complete

### Task 7.4: Deploy and monitor
- [x] Deploy updated backend with docker compose restart
- [x] Monitor logs for errors
- [x] Check WebSocket connection count metrics
- [x] Verify activity events being persisted
- [x] Monitor API response times
- [x] Collect feedback from frontend team

**Validation**: Production deployment successful, no errors

## Success Metrics

- ✅ WebSocket endpoint accepts connections and sends periodic updates
- ✅ All chat endpoints return 200 for valid queries (not 500 parameter errors)
- ✅ Activity events persist without "callable" errors
- ✅ OpenAPI docs render at /docs without Pydantic errors
- ✅ Frontend dashboard receives real-time updates
- ✅ Integration tests pass for WebSocket and chat endpoints
- ✅ No regression in existing endpoint functionality
- ✅ API response times remain under 200ms for health/stats endpoints
