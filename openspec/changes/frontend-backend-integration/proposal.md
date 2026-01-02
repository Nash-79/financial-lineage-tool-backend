# Frontend-Backend Integration Proposal

## Why

The backend currently has integration issues that prevent the frontend from connecting properly:

1. **Missing WebSocket Endpoint**: The frontend expects `ws://localhost:8000/api/v1/ws/dashboard` for real-time updates, but the backend returns 403 Forbidden. The endpoint doesn't exist with proper WebSocket handling.

2. **Missing Admin Restart Endpoint**: The frontend expects `POST /admin/restart` to trigger container restarts, but the backend returns 404 Not Found. The endpoint doesn't exist.

3. **Chat Endpoint Bugs**: All chat endpoints (`/api/chat/text`, `/api/chat/semantic`, `/api/chat/graph`, `/api/chat/deep`) are broken due to missing `model` parameter in `ollama.generate()` calls (Status: FIXED in chat.py).

4. **Activity Persistence Failures**: Activity tracking middleware is failing with "first argument must be callable or None" errors, preventing proper event logging.

5. **Pydantic Schema Errors**: OpenAPI schema generation fails with forward reference errors, potentially affecting frontend API client generation.

These issues prevent the frontend dashboard from:
- Receiving real-time updates via WebSocket
- Restarting the backend container when needed
- Making successful chat queries
- Tracking user activity properly
- Generating accurate TypeScript API clients from OpenAPI spec

## What

This proposal adds:

1. **WebSocket Dashboard Endpoint** (`/api/v1/ws/dashboard`):
   - Real-time connection for frontend dashboard
   - Broadcasts system events (ingestion status, query completion, errors)
   - Sends periodic stats updates
   - Proper connection authentication and error handling

2. **Admin Restart Endpoint** (`/admin/restart`):
   - POST endpoint to trigger graceful API container restart
   - Returns `{"status": "restarting"}` response
   - Uses Docker restart policy to bring container back up
   - Frontend testing shows this endpoint is missing (returns 404)

3. **Chat Endpoint Fixes** (COMPLETED):
   - ✅ Fixed all `ollama.generate()` calls to include `model=config.LLM_MODEL`
   - Verified parameter signatures match OllamaClient interface

4. **Activity Tracker Fixes**:
   - Fix middleware initialization to accept proper callback functions
   - Ensure activity events persist to storage/logs
   - Add error handling for persistence failures

5. **Pydantic Model Fixes**:
   - Resolve forward reference issues in API models
   - Ensure all models are fully defined before schema generation
   - Verify OpenAPI schema renders correctly at `/docs`

## Scope

**In Scope:**
- WebSocket endpoint implementation in `src/api/routers/admin.py`
- Admin restart endpoint implementation in `src/api/routers/admin.py`
- Activity tracker middleware fixes
- Pydantic model fixes for schema generation
- Integration tests for WebSocket, restart, and chat endpoints
- Documentation updates for WebSocket and admin endpoints

**Out of Scope:**
- Frontend URL construction fixes (handled in frontend repo)
- Advanced WebSocket features (rooms, authentication, message queuing)
- Real-time graph visualization updates
- WebSocket connection pooling/scaling

## Impact

**Benefits:**
- ✅ Frontend can connect to real-time dashboard updates
- ✅ Frontend can restart backend container via admin endpoint
- ✅ Chat endpoints functional for Q&A features
- ✅ Activity tracking works for user metrics
- ✅ OpenAPI docs render properly for API client generation

**Risks:**
- WebSocket connections consume server resources (mitigated by connection limits)
- Activity tracking may impact performance (mitigated by async persistence)

## Dependencies

- FastAPI WebSocket support (already included)
- Existing middleware infrastructure
- Pydantic 2.x (already in use)

## Spec Deltas

1. **websocket-dashboard**: New spec for WebSocket endpoint requirements
2. **api-endpoints**: MODIFIED to add WebSocket connection scenario
