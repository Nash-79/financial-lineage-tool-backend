from fastapi import FastAPI

from src.utils import otel as otel_module


def test_setup_otel_disabled() -> None:
    otel_module._otel_initialized = False
    app = FastAPI()
    assert (
        otel_module.setup_otel(
            app,
            enabled=False,
            service_name="test-service",
            otlp_endpoint="",
        )
        is False
    )


def test_setup_otel_enabled() -> None:
    otel_module._otel_initialized = False
    app = FastAPI()
    expected = otel_module.OTEL_AVAILABLE
    assert (
        otel_module.setup_otel(
            app,
            enabled=True,
            service_name="test-service",
            otlp_endpoint="http://localhost:4318",
        )
        is expected
    )
