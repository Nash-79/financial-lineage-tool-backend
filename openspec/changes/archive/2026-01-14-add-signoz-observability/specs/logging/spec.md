## ADDED Requirements
### Requirement: OpenTelemetry Export
The system SHALL export logs, traces, and metrics via OTLP when enabled.

#### Scenario: OTLP export enabled
- **WHEN** OTEL_EXPORTER_OTLP_ENDPOINT is configured
- **THEN** the system exports traces and logs to the OTLP endpoint
- **AND** the service name is included in telemetry attributes
- **AND** export failures are logged without crashing the API

### Requirement: Structured Log Export
The system SHALL forward structured logs to the OpenTelemetry pipeline.

#### Scenario: Log forwarding
- **WHEN** the API emits logs
- **THEN** logs are forwarded to OTLP as log records
- **AND** logs include level, message, and module context
