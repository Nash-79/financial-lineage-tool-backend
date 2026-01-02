"""
Validation utilities for Financial Lineage Tool.

This module provides validation functions for input data, configuration,
and other application data to ensure data integrity.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .exceptions import ValidationError


def validate_file_path(file_path: str, must_exist: bool = True) -> Path:
    """
    Validate file path and return Path object.

    Args:
        file_path: Path to validate
        must_exist: If True, file must exist

    Returns:
        Path object

    Raises:
        ValidationError: If validation fails
    """
    path = Path(file_path)

    if must_exist and not path.exists():
        raise ValidationError(f"File does not exist: {file_path}")

    return path


def validate_env_var(var_name: str, required: bool = True) -> Optional[str]:
    """
    Validate environment variable exists and return its value.

    Args:
        var_name: Environment variable name
        required: If True, variable must be set

    Returns:
        Environment variable value or None

    Raises:
        ValidationError: If required variable is missing
    """
    value = os.getenv(var_name)

    if required and not value:
        raise ValidationError(f"Required environment variable not set: {var_name}")

    return value


def validate_port(port: int) -> int:
    """
    Validate port number is in valid range.

    Args:
        port: Port number to validate

    Returns:
        Valid port number

    Raises:
        ValidationError: If port is invalid
    """
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValidationError(f"Invalid port number: {port}. Must be 1-65535")

    return port


def validate_config(config: Dict[str, Any], required_keys: list[str]) -> None:
    """
    Validate configuration dictionary has required keys.

    Args:
        config: Configuration dictionary
        required_keys: List of required key names

    Raises:
        ValidationError: If required keys are missing
    """
    missing = [key for key in required_keys if key not in config]

    if missing:
        raise ValidationError(f"Missing required configuration keys: {missing}")
