## ADDED Requirements
### Requirement: SigNoz Local Stack
The system SHALL provide a Docker Compose stack to run SigNoz locally.

#### Scenario: Start SigNoz stack
- **WHEN** developers run the SigNoz docker compose file
- **THEN** SigNoz services start successfully on localhost
- **AND** the UI is accessible without additional configuration
- **AND** the OTLP endpoint is available for the backend to export telemetry
