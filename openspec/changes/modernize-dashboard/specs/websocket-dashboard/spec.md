## ADDED Requirements

### Requirement: Consolidated System Status API

The system SHALL provide a consolidated status endpoint at `/api/v1/system/status` aggregating health information from all subsystems.

#### Scenario: Fetch complete system status

- **WHEN** client calls `GET /api/v1/system/status`
- **THEN** response includes overall_status as "healthy", "degraded", or "unhealthy"
- **AND** response includes services object with status for ollama, qdrant, neo4j, redis, openrouter
- **AND** response includes database object with duckdb mode, connection info, and snapshot status
- **AND** response includes models object with configuration completeness
- **AND** response includes logs object with 24h category summaries
- **AND** response includes features object with active feature flags

#### Scenario: System status caching

- **WHEN** multiple clients request system status within 10 seconds
- **THEN** backend returns cached response without re-querying all services
- **AND** cache is invalidated after 10 seconds
- **AND** response includes cache_age_seconds field

#### Scenario: Partial service unavailability

- **WHEN** one or more non-critical services are unavailable
- **THEN** response still returns with overall_status as "degraded"
- **AND** unavailable services show status "unavailable" with error message
- **AND** available services show their actual status
- **AND** response does not fail or timeout

### Requirement: Model Availability Status API

The system SHALL provide model availability information at `/api/v1/models/availability` showing per-chat-mode readiness.

#### Scenario: Fetch model availability

- **WHEN** client calls `GET /api/v1/models/availability`
- **THEN** response includes chat_modes object with status for deep, semantic, graph, text
- **AND** each chat mode shows "ready", "degraded", or "unavailable" status
- **AND** response includes providers object showing ollama and openrouter availability
- **AND** response includes lists of configured and missing usage types

#### Scenario: Chat mode without configuration

- **WHEN** a chat mode has no active model configuration
- **THEN** that chat mode shows status "unavailable"
- **AND** response includes reason field explaining missing configuration
- **AND** other configured chat modes remain unaffected

#### Scenario: Provider offline affects availability

- **WHEN** Ollama service is offline
- **THEN** chat modes depending on Ollama show status "unavailable" or "degraded"
- **AND** chat modes with OpenRouter fallback show status "degraded" (not unavailable)
- **AND** provider status shows ollama as "offline"

### Requirement: Log Summary API

The system SHALL provide log summary statistics at `/api/v1/logs/summary` for dashboard display.

#### Scenario: Fetch log summary

- **WHEN** client calls `GET /api/v1/logs/summary`
- **THEN** response includes per-category counts for app, chat, audit, ingestion
- **AND** each category shows total_count, error_count, warning_count
- **AND** response includes total_entries and total_errors across all categories
- **AND** response includes period_hours indicating time window (default 24)

#### Scenario: Include latest error for visibility

- **WHEN** errors exist in the summary period
- **THEN** response includes latest_error object with timestamp, category, level, message
- **AND** message is truncated to 200 characters if longer
- **AND** latest_error is null if no errors in period

#### Scenario: Empty log directory handling

- **WHEN** a log category has no files
- **THEN** that category shows total_count 0, error_count 0
- **AND** response does not fail or return error
- **AND** other categories with files return their counts

## MODIFIED Requirements

### Requirement: Dashboard stats reflect live backend state

The system SHALL compute dashboard stats from live graph and file metadata sources, enhanced with system status information.

#### Scenario: Stats update uses live counts

- **WHEN** frontend calls `GET /api/v1/stats` or receives a `stats_update` message
- **THEN** node and file counts reflect current graph and DuckDB metadata
- **AND** the payload includes `filesProcessed` derived from file metadata
- **AND** the payload format matches the dashboard UI expectations

#### Scenario: Stats include system health summary

- **WHEN** frontend calls `GET /api/v1/stats`
- **THEN** response includes optional `system_health` field
- **AND** system_health contains service_count_healthy and service_count_total
- **AND** system_health contains model_configs_complete boolean
- **AND** system_health contains recent_errors_24h count

### Requirement: WebSocket Dashboard Connection

System MUST provide WebSocket endpoint for real-time dashboard updates at `/admin/ws/dashboard` with enhanced system status events.

#### Scenario: Establishing WebSocket connection

- **WHEN** frontend connects to ws://127.0.0.1:8000/admin/ws/dashboard
- **THEN** backend accepts WebSocket connection
- **AND** sends connection_ack message with timestamp
- **AND** connection remains open for bidirectional communication

#### Scenario: Receiving periodic stats updates

- **WHEN** WebSocket connection is established
- **THEN** backend sends stats_update message every 5 seconds
- **AND** message contains current dashboard statistics
- **AND** statistics match /api/v1/stats endpoint data
- **AND** message includes timestamp for ordering

#### Scenario: Receiving system status changes

- **WHEN** a service status changes (e.g., Ollama becomes unavailable)
- **THEN** backend broadcasts system_status_change event
- **AND** event includes service name, old status, new status
- **AND** event includes timestamp
- **AND** frontend can update status indicators without polling

#### Scenario: Receiving model configuration changes

- **WHEN** model configuration is added, updated, or deleted
- **THEN** backend broadcasts model_config_change event
- **AND** event includes usage_type affected
- **AND** event includes change_type as "added", "updated", or "deleted"
- **AND** frontend can refresh model availability display
