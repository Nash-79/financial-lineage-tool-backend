## ADDED Requirements
### Requirement: Dashboard stats reflect live backend state
The system SHALL compute dashboard stats from live graph and file metadata sources.

#### Scenario: Stats update uses live counts
- **WHEN** frontend calls `GET /api/v1/stats` or receives a `stats_update` message
- **THEN** node and file counts reflect current graph and DuckDB metadata
- **AND** the payload includes `filesProcessed` derived from file metadata
- **AND** the payload format matches the dashboard UI expectations
