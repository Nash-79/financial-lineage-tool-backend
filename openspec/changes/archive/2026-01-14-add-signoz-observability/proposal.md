# Change: Add SigNoz Observability via OpenTelemetry

## Why
We need a free, Grafana-less observability stack that centralizes logs, traces, and metrics across the backend. SigNoz provides a self-hosted UI and OTLP ingestion that aligns with our local-first usage.

## What Changes
- Add OpenTelemetry SDK/instrumentation for FastAPI, HTTPX, and logging.
- Export logs, traces, and metrics via OTLP to a local SigNoz collector.
- Provide a Docker Compose stack to run SigNoz locally.

## Impact
- Affected specs: logging, deployment
- Affected code: src/api/main_local.py, logging config, dependency lists, new docker compose file
