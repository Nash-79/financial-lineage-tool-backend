from typing import List, Dict, Optional
import logging
from .duckdb_client import get_duckdb_client
from ..config.sql_dialects import SQL_DIALECTS as DEFAULT_DIALECTS

logger = logging.getLogger(__name__)


class SqlDialectRepository:
    """
    Repository for SQL dialects, backed by DuckDB with fallback to in-memory defaults.
    """

    def get_all(self) -> List[Dict]:
        """Get all dialects."""
        try:
            client = get_duckdb_client()
            results = client.fetchall(
                """
                SELECT id, display_name, sqlglot_read_key, enabled, is_default, description
                FROM sql_dialects
            """
            )

            if not results:
                # Table exists but empty? Fallback/seed
                return list(DEFAULT_DIALECTS.values())

            dialects = []
            for row in results:
                dialects.append(
                    {
                        "id": row[0],
                        "display_name": row[1],
                        "sqlglot_read_key": row[2],
                        "enabled": bool(row[3]),
                        "is_default": bool(row[4]),
                        "description": row[5],
                    }
                )
            return dialects

        except Exception as e:
            logger.warning(
                f"Failed to load dialects from DuckDB ({e}). Using defaults."
            )
            return list(DEFAULT_DIALECTS.values())

    def get_enabled(self) -> List[Dict]:
        """Get enabled dialects."""
        all_dialects = self.get_all()
        return [d for d in all_dialects if d["enabled"]]

    def get_default(self) -> Dict:
        """Get default dialect."""
        all_dialects = self.get_all()
        for d in all_dialects:
            if d["is_default"]:
                return d
        # Fallback to tsql if valid, else first one
        for d in all_dialects:
            if d["id"] == "tsql":
                return d
        return all_dialects[0] if all_dialects else DEFAULT_DIALECTS["tsql"]

    def get_by_id(self, dialect_id: str) -> Optional[Dict]:
        """Get dialect by ID."""
        all_dialects = self.get_all()
        for d in all_dialects:
            if d["id"] == dialect_id:
                return d
        return None
