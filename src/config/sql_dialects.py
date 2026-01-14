"""
SQL Dialect Configuration and Registry

Provides helpers for managing SQL dialect selection and validation.
Dialects are backed by sqlglot's dialect support.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# Supported SQL dialects registry
# Maps display names to sqlglot dialect keys
SQL_DIALECTS = {
    "tsql": {
        "id": "tsql",
        "display_name": "T-SQL (SQL Server)",
        "sqlglot_read_key": "tsql",
        "enabled": True,
        "is_default": True,
        "description": "Microsoft SQL Server / Azure SQL",
    },
    "postgres": {
        "id": "postgres",
        "display_name": "PostgreSQL",
        "sqlglot_read_key": "postgres",
        "enabled": True,
        "is_default": False,
        "description": "PostgreSQL database",
    },
    "mysql": {
        "id": "mysql",
        "display_name": "MySQL",
        "sqlglot_read_key": "mysql",
        "enabled": True,
        "is_default": False,
        "description": "MySQL database",
    },
    "duckdb": {
        "id": "duckdb",
        "display_name": "DuckDB",
        "sqlglot_read_key": "duckdb",
        "enabled": True,
        "is_default": False,
        "description": "DuckDB analytical database",
    },
    "spark": {
        "id": "spark",
        "display_name": "Spark SQL",
        "sqlglot_read_key": "spark",
        "enabled": True,
        "is_default": False,
        "description": "Apache Spark SQL",
    },
    "bigquery": {
        "id": "bigquery",
        "display_name": "BigQuery",
        "sqlglot_read_key": "bigquery",
        "enabled": True,
        "is_default": False,
        "description": "Google BigQuery",
    },
    "snowflake": {
        "id": "snowflake",
        "display_name": "Snowflake",
        "sqlglot_read_key": "snowflake",
        "enabled": True,
        "is_default": False,
        "description": "Snowflake data warehouse",
    },
    "oracle": {
        "id": "oracle",
        "display_name": "Oracle",
        "sqlglot_read_key": "oracle",
        "enabled": True,
        "is_default": False,
        "description": "Oracle Database",
    },
    "fabric": {
        "id": "fabric",
        "display_name": "Microsoft Fabric",
        "sqlglot_read_key": "tsql",
        "enabled": True,
        "is_default": False,
        "description": "Microsoft Fabric (T-SQL compatible)",
    },
}


def _get_repo():
    """Helper to get repository instance locally to avoid circular imports."""
    from src.storage.dialect_store import SqlDialectRepository

    return SqlDialectRepository()


def get_all_dialects() -> List[Dict]:
    """Get all available SQL dialects."""
    return _get_repo().get_all()


def get_enabled_dialects() -> List[Dict]:
    """Get all enabled SQL dialects."""
    return _get_repo().get_enabled()


def get_enabled_dialect_ids() -> List[str]:
    """Get enabled SQL dialect IDs."""
    return [dialect["id"] for dialect in get_enabled_dialects()]


def get_default_dialect() -> Dict:
    """Get the default SQL dialect."""
    return _get_repo().get_default()


def get_dialect_by_id(dialect_id: str) -> Optional[Dict]:
    """Get dialect configuration by ID."""
    return _get_repo().get_by_id(dialect_id)


def validate_dialect(dialect_id: str) -> bool:
    """Validate that a dialect ID is supported and enabled."""
    if dialect_id == "auto":
        return True
    dialect = get_dialect_by_id(dialect_id)
    return dialect is not None and dialect["enabled"]


def resolve_dialect_for_parsing(dialect_id: str) -> str:
    """
    Resolve a dialect ID to its sqlglot read key for parsing.

    Args:
        dialect_id: Dialect identifier (e.g., 'tsql', 'postgres')

    Returns:
        sqlglot read key string

    Raises:
        ValueError: If dialect is invalid or not enabled
    """
    if dialect_id == "auto":
        # Auto mode: use default dialect
        logger.info("Auto dialect mode: using default")
        return get_default_dialect()["sqlglot_read_key"]

    dialect = get_dialect_by_id(dialect_id)
    if not dialect:
        raise ValueError(f"Unknown SQL dialect: {dialect_id}")

    if not dialect["enabled"]:
        raise ValueError(f"SQL dialect '{dialect_id}' is not enabled")

    return dialect["sqlglot_read_key"]


def format_dialect_error(dialect_id: str) -> str:
    """Build a consistent error message for unsupported dialects."""
    enabled_ids = get_enabled_dialect_ids()
    available = ", ".join(enabled_ids) if enabled_ids else "none"
    return (
        f"Unsupported SQL dialect: {dialect_id}. "
        f"Available dialects: {available}. "
        "See /api/v1/config/sql-dialects"
    )
