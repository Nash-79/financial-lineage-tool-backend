## ADDED Requirements
### Requirement: Frontend uses backend data sources
The frontend SHALL use backend APIs for files, stats, and lineage instead of mock data.

#### Scenario: Files page uses live endpoints
- **WHEN** backend file endpoints respond successfully
- **THEN** the Files page renders data from `/api/v1/files` and `/api/v1/files/stats`
- **AND** mock data is not shown
- **AND** search queries call `/api/v1/files/search`

### Requirement: Dashboard wiring and connection state
The frontend SHALL connect to backend dashboard endpoints and expose connection status.

#### Scenario: Dashboard uses stats and WebSocket config
- **WHEN** the Dashboard page loads
- **THEN** it calls `/api/v1/stats` for initial metrics
- **AND** it resolves the WebSocket URL from `/api/v1/config/websocket`
- **AND** it shows connection state for the WebSocket stream

### Requirement: Database page visibility for ingested assets
The frontend SHALL display ingested assets from backend lineage and file metadata.

#### Scenario: Database page shows SQL and Python assets
- **WHEN** a user opens the Database page
- **THEN** the page fetches lineage nodes/edges and file metadata
- **AND** SQL and Python assets are visible after ingestion completes
- **AND** assets link back to their source files and runs

### Requirement: Health warnings for missing dependencies
The frontend SHALL surface warnings when backend dependencies are unavailable.

#### Scenario: Dependency health warning
- **WHEN** `/health` reports degraded or unreachable services
- **THEN** the UI shows a warning banner naming the unavailable services
- **AND** actions that require those services are disabled or annotated
