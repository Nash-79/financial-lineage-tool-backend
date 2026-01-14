# SigNoz Setup (Local)

This guide runs a local SigNoz stack and wires the backend to export OTLP logs, traces, and metrics.

## 1. Start SigNoz

```bash
docker compose -f docker-compose.signoz.yml up -d
```

- UI: `http://localhost:3301`
- OTLP gRPC: `http://localhost:4317`
- OTLP HTTP: `http://localhost:4318`

## 2. Enable OTLP export in the backend

```bash
export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=financial-lineage-backend
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

Restart the API after setting the variables.

## 3. Verify in SigNoz

- Open the UI at `http://localhost:3301`
- Navigate to Services and confirm the backend service appears
- Check logs, traces, and metrics for recent requests

## Notes

- The OTLP export is optional; leave `OTEL_ENABLED=false` to disable.
- The existing `/metrics` endpoint remains available for Prometheus scraping if needed.
