## Context
Introduce a local observability stack that replaces Grafana and centralizes telemetry for logs, traces, and metrics.

## Decisions
- Use SigNoz with OTLP ingestion for local deployments.
- Configure OpenTelemetry in the API process via environment variables.

## Risks / Trade-offs
- Additional containers and resource usage during local development.

## Migration Plan
- Add optional compose file and env flags; default remains no OTLP export.

## Open Questions
- Should we also emit existing Prometheus metrics via OTLP or keep both exporters?
