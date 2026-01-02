"""Ingestion endpoint models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request model for file ingestion."""

    file_path: str = Field(..., description="Path to file or directory")
    file_type: str = Field(default="sql", description="File type (sql, python)")


class SqlIngestRequest(BaseModel):
    """Request model for SQL content ingestion."""

    sql_content: str = Field(
        ..., description="Raw SQL content to be parsed and ingested."
    )
    dialect: str = Field(
        default="tsql", description="The SQL dialect (e.g., tsql, spark, bigquery)."
    )
    source_file: str = Field(
        default="manual_ingest",
        description="The original file name or source of the SQL.",
    )
