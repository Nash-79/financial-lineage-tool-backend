"""
Logging configuration for Financial Lineage Tool.

This module sets up structured logging with consistent formatting across
the application, supporting multiple output formats and log levels.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from .constants import DEFAULT_LOG_LEVEL, LOG_FORMAT


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None,
    include_request_id: bool = True,
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to env var or INFO.
        format_string: Custom log format string. Defaults to standard format.
        include_request_id: Whether to include request ID in logs.

    Example:
        >>> setup_logging(level="DEBUG")
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    # Get log level from env or parameter
    log_level = level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)

    # Convert string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Use custom format or default
    log_format = format_string or LOG_FORMAT

    # If request ID not needed, use simpler format
    if not include_request_id:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any existing configuration
    )

    # Set third-party library log levels to reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


class RequestIDFilter(logging.Filter):
    """
    Logging filter that adds request ID to log records.

    This filter checks if the record has a request_id attribute,
    and adds a default value if not present.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request_id to log record.

        Args:
            record: Log record to filter

        Returns:
            Always True (don't filter out any records)
        """
        if not hasattr(record, "request_id"):
            record.request_id = "-"  # Default value when no request context
        return True
