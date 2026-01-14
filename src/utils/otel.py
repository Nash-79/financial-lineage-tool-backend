"""
OpenTelemetry setup for optional SigNoz export.

This module wires traces, logs, and metrics to an OTLP endpoint when enabled.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI

OTEL_AVAILABLE = True
_otel_import_error: Optional[Exception] = None

try:
    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    try:
        from opentelemetry.exporter.otlp.proto.http.log_exporter import OTLPLogExporter
    except ImportError:  # pragma: no cover - fallback for older exporter layout
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError as exc:
    OTEL_AVAILABLE = False
    _otel_import_error = exc

logger = logging.getLogger(__name__)
_otel_initialized = False


def _normalize_endpoint(base_endpoint: str, path: str) -> str:
    base = base_endpoint.rstrip("/")
    if base.endswith(path):
        return base
    return f"{base}{path}"


def setup_otel(
    app: FastAPI,
    *,
    enabled: bool,
    service_name: str,
    otlp_endpoint: Optional[str],
) -> bool:
    """Initialize OpenTelemetry exporters and instrumentation."""
    global _otel_initialized
    if _otel_initialized:
        return True
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry unavailable: %s", _otel_import_error)
        return False
    if not enabled or not otlp_endpoint:
        logger.info(
            "OpenTelemetry disabled (set OTEL_ENABLED=true and OTEL_EXPORTER_OTLP_ENDPOINT)."
        )
        return False

    try:
        resource = Resource.create({SERVICE_NAME: service_name})

        traces_endpoint = _normalize_endpoint(otlp_endpoint, "/v1/traces")
        metrics_endpoint = _normalize_endpoint(otlp_endpoint, "/v1/metrics")
        logs_endpoint = _normalize_endpoint(otlp_endpoint, "/v1/logs")

        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint))
        )
        trace.set_tracer_provider(trace_provider)

        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=metrics_endpoint)
        )
        metrics.set_meter_provider(
            MeterProvider(resource=resource, metric_readers=[metric_reader])
        )

        log_provider = LoggerProvider(resource=resource)
        log_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=logs_endpoint))
        )
        set_logger_provider(log_provider)
        logging.getLogger().addHandler(
            LoggingHandler(level=logging.INFO, logger_provider=log_provider)
        )

        LoggingInstrumentor().instrument(set_logging_format=True)
        HTTPXClientInstrumentor().instrument()
        FastAPIInstrumentor.instrument_app(app)

        _otel_initialized = True
        logger.info("OpenTelemetry enabled with OTLP endpoint %s", otlp_endpoint)
        return True
    except Exception as exc:
        logger.error("Failed to initialize OpenTelemetry: %s", exc, exc_info=True)
        return False
