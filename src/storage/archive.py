"""
Parquet archiving utilities for metadata.

Uses DuckDB's native Parquet export capabilities with Snappy compression.
Archives can be queried directly using DuckDB's Parquet reader.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .duckdb_client import get_duckdb_client

logger = logging.getLogger(__name__)


def get_archive_dir(archive_month: Optional[str] = None) -> Path:
    """
    Get archive directory path for given month.

    Args:
        archive_month: Month in YYYY-MM format. Defaults to current month.

    Returns:
        Path to archive directory
    """
    if not archive_month:
        archive_month = datetime.now().strftime("%Y-%m")

    return Path("data/archives") / archive_month


def export_to_parquet(
    archive_month: Optional[str] = None, tables: Optional[list[str]] = None
) -> dict:
    """
    Export metadata tables to Parquet files.

    Uses DuckDB COPY TO command with Snappy compression for efficient storage.

    Args:
        archive_month: Month in YYYY-MM format. Defaults to current month.
        tables: List of tables to export. Defaults to all metadata tables.

    Returns:
        Dict with export results including paths and row counts
    """
    client = get_duckdb_client()
    archive_dir = get_archive_dir(archive_month)

    # Create archive directory
    archive_dir.mkdir(parents=True, exist_ok=True)

    if tables is None:
        tables = ["projects", "repositories", "links"]

    results = {
        "archive_path": str(archive_dir),
        "archive_month": archive_month or datetime.now().strftime("%Y-%m"),
        "tables": {},
    }

    for table in tables:
        output_path = archive_dir / f"metadata_{table}.parquet"

        try:
            # Get row count before export
            count_result = client.fetchone(f"SELECT COUNT(*) FROM {table}")
            row_count = count_result[0] if count_result else 0

            if row_count == 0:
                logger.info(f"Skipping empty table: {table}")
                results["tables"][table] = {
                    "path": None,
                    "row_count": 0,
                    "skipped": True,
                }
                continue

            # Export using DuckDB COPY TO with Snappy compression
            client.execute_read(
                f"""
                COPY {table} TO '{output_path}'
                (FORMAT PARQUET, COMPRESSION SNAPPY)
            """
            )

            # Get file size
            file_size = output_path.stat().st_size if output_path.exists() else 0

            results["tables"][table] = {
                "path": str(output_path),
                "row_count": row_count,
                "file_size_bytes": file_size,
            }

            logger.info(f"Exported {table}: {row_count} rows to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export table {table}: {e}")
            results["tables"][table] = {
                "path": None,
                "row_count": 0,
                "error": str(e),
            }

    return results


def query_archived_parquet(
    archive_month: str, query: str, table: str = "projects"
) -> list[tuple]:
    """
    Query archived Parquet files using DuckDB.

    DuckDB can query Parquet files directly without loading into memory,
    using predicate pushdown for efficient filtering.

    Args:
        archive_month: Month in YYYY-MM format
        query: WHERE clause for filtering (without 'WHERE' keyword)
        table: Table name (projects, repositories, links)

    Returns:
        List of result tuples

    Example:
        >>> query_archived_parquet("2024-01", "name LIKE '%test%'", "projects")
    """
    client = get_duckdb_client()
    archive_dir = get_archive_dir(archive_month)
    parquet_path = archive_dir / f"metadata_{table}.parquet"

    if not parquet_path.exists():
        logger.warning(f"Archive not found: {parquet_path}")
        return []

    try:
        result = client.fetchall(
            f"""
            SELECT * FROM read_parquet('{parquet_path}')
            WHERE {query}
        """
        )
        return result
    except Exception as e:
        logger.error(f"Failed to query archive: {e}")
        raise


def list_archives() -> list[dict]:
    """
    List all available archive directories.

    Returns:
        List of archive info dicts with month, file count, and total size
    """
    archives_root = Path("data/archives")

    if not archives_root.exists():
        return []

    archives = []

    for month_dir in sorted(archives_root.iterdir(), reverse=True):
        if not month_dir.is_dir():
            continue

        parquet_files = list(month_dir.glob("*.parquet"))
        total_size = sum(f.stat().st_size for f in parquet_files)

        archives.append(
            {
                "month": month_dir.name,
                "file_count": len(parquet_files),
                "total_size_bytes": total_size,
                "files": [f.name for f in parquet_files],
            }
        )

    return archives


def query_across_archives(
    query: str, table: str = "projects", months: Optional[list[str]] = None
) -> list[tuple]:
    """
    Query across multiple archived Parquet files using UNION.

    Args:
        query: WHERE clause for filtering (without 'WHERE' keyword)
        table: Table name (projects, repositories, links)
        months: List of months to query. If None, queries all available archives.

    Returns:
        Combined list of result tuples
    """
    client = get_duckdb_client()
    archives_root = Path("data/archives")

    if months is None:
        # Get all available archive months
        archives = list_archives()
        months = [a["month"] for a in archives]

    if not months:
        return []

    # Build UNION query across all archives
    parquet_files = []
    for month in months:
        parquet_path = archives_root / month / f"metadata_{table}.parquet"
        if parquet_path.exists():
            parquet_files.append(str(parquet_path))

    if not parquet_files:
        return []

    try:
        # Use DuckDB's ability to read multiple Parquet files
        files_list = ", ".join(f"'{f}'" for f in parquet_files)
        result = client.fetchall(
            f"""
            SELECT * FROM read_parquet([{files_list}])
            WHERE {query}
        """
        )
        return result
    except Exception as e:
        logger.error(f"Failed to query archives: {e}")
        raise


def cleanup_old_data(archive_month: str, table: str, filter_query: str) -> int:
    """
    Delete data from active DuckDB table after successful archive.

    Only deletes rows matching the filter query.

    Args:
        archive_month: Month that was archived
        table: Table name
        filter_query: WHERE clause to match archived rows

    Returns:
        Number of deleted rows
    """
    client = get_duckdb_client()

    try:
        # Get count before delete
        count_result = client.fetchone(
            f"SELECT COUNT(*) FROM {table} WHERE {filter_query}"
        )
        count = count_result[0] if count_result else 0

        if count > 0:
            # This should be wrapped in execute_write for proper locking
            # but for now we'll use direct execute as it requires sync context
            client.conn.execute(f"DELETE FROM {table} WHERE {filter_query}")
            logger.info(f"Deleted {count} archived rows from {table}")

        return count
    except Exception as e:
        logger.error(f"Failed to cleanup archived data: {e}")
        raise
