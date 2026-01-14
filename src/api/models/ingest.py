"""Ingestion endpoint models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request model for file ingestion."""

    file_path: str = Field(..., description="Path to file or directory")
    file_type: str = Field(default="sql", description="File type (sql, python)")
    dialect: str = Field(
        default="auto",
        description="SQL dialect for parsing (e.g., tsql, spark, bigquery).",
    )
    project_id: Optional[str] = Field(
        default=None, description="Project ID for context injection into LLM prompts"
    )


class SqlIngestRequest(BaseModel):
    """Request model for SQL content ingestion."""

    sql_content: str = Field(
        ..., description="Raw SQL content to be parsed and ingested."
    )
    dialect: str = Field(
        default="auto", description="The SQL dialect (e.g., tsql, spark, bigquery)."
    )
    source_file: str = Field(
        default="manual_ingest",
        description="The original file name or source of the SQL.",
    )
    project_id: Optional[str] = Field(
        default=None, description="Project ID for context injection into LLM prompts"
    )


class SqlIngestResponse(BaseModel):
    """Response model for SQL content ingestion."""

    status: str
    source: str
    context_applied: bool = Field(
        default=False,
        description="Whether project context was successfully injected into the LLM prompt",
    )
