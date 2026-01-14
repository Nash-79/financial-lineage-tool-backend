"""CORS middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI application.

    Args:
        app: FastAPI application instance to configure.

    Note:
        Currently allows all origins for development. In production,
        restrict to specific domains.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080/",
            "null",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
