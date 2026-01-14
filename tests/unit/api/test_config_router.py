import pytest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import config as config_router

app = FastAPI()
app.include_router(config_router.router)
client = TestClient(app)


@pytest.mark.asyncio
async def test_get_sql_dialects_returns_list():
    sample = [
        {
            "id": "tsql",
            "display_name": "T-SQL (SQL Server)",
            "sqlglot_read_key": "tsql",
            "enabled": True,
            "is_default": True,
        },
        {
            "id": "duckdb",
            "display_name": "DuckDB",
            "sqlglot_read_key": "duckdb",
            "enabled": True,
            "is_default": False,
        },
    ]

    with patch("src.config.sql_dialects.get_enabled_dialects", return_value=sample):
        response = client.get("/api/v1/config/sql-dialects")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "tsql"
    assert data[0]["sqlglot_key"] == "tsql"
