"""API models for configuration endpoints."""

from pydantic import BaseModel, Field


class SQLDialect(BaseModel):
    """SQL dialect configuration for frontend selection."""

    id: str = Field(..., description="Dialect identifier (e.g., tsql, postgres)")
    display_name: str = Field(..., description="Human-readable dialect name")
    sqlglot_key: str = Field(..., description="sqlglot read key for parsing")
    is_default: bool = Field(False, description="Whether this dialect is default")
    enabled: bool = Field(True, description="Whether this dialect is enabled")
