"""Database schema models."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel


class DatabaseSchema(BaseModel):
    """Database schema metadata model."""

    name: str
    tables: List[str]
    views: List[str] = []
    procedures: List[str] = []
    last_updated: str
