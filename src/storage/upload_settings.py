"""Upload settings persistence store.

Manages file upload configuration (allowed extensions, file size limits) in DuckDB.
Settings persist across server restarts.
"""

import json
import logging
from typing import Dict, List, Optional

from .duckdb_client import get_duckdb_client
from ..api.config import config

logger = logging.getLogger(__name__)


class UploadSettingsStore:
    """Store for persistent upload settings."""

    def __init__(self):
        """Initialize upload settings store."""
        self.db = get_duckdb_client()

    def get_settings(self) -> Optional[Dict]:
        """
        Load upload settings from database.

        Returns:
            Dictionary with settings or None if not found.
        """
        if not self.db:
            logger.warning("DuckDB not initialized, cannot load upload settings")
            return None

        try:
            result = self.db.fetchone(
                """
                SELECT allowed_extensions, max_file_size_mb, updated_at, updated_by
                FROM upload_settings
                WHERE id = 'default'
                """
            )

            if not result:
                return None

            return {
                "allowed_extensions": result[0],  # JSON string
                "max_file_size_mb": result[1],
                "updated_at": result[2].isoformat() if result[2] else None,
                "updated_by": result[3],
            }

        except Exception as e:
            logger.error(f"Failed to load upload settings: {e}")
            return None

    async def save_settings(
        self,
        allowed_extensions: List[str],
        max_file_size_mb: int,
        updated_by: str = "api",
    ) -> bool:
        """
        Save upload settings to database.

        Args:
            allowed_extensions: List of allowed file extensions (e.g., [".sql", ".py"])
            max_file_size_mb: Maximum file size in MB
            updated_by: Who updated the settings (default: "api")

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.db:
            logger.error("DuckDB not initialized, cannot save upload settings")
            return False

        try:
            # Convert extensions list to JSON string
            extensions_json = json.dumps(allowed_extensions)

            # Upsert settings (single row with id='default')
            # First, check if row exists
            existing = self.db.fetchone(
                "SELECT id FROM upload_settings WHERE id = 'default'"
            )

            if existing:
                # Update existing row
                await self.db.execute_write(
                    """
                    UPDATE upload_settings
                    SET allowed_extensions = ?,
                        max_file_size_mb = ?,
                        updated_by = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = 'default'
                    """,
                    (extensions_json, max_file_size_mb, updated_by),
                )
            else:
                # Insert new row
                await self.db.execute_write(
                    """
                    INSERT INTO upload_settings (id, allowed_extensions, max_file_size_mb, updated_by)
                    VALUES ('default', ?, ?, ?)
                    """,
                    (extensions_json, max_file_size_mb, updated_by),
                )

            logger.info(
                f"Saved upload settings: extensions={allowed_extensions}, max_size={max_file_size_mb}MB, by={updated_by}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save upload settings: {e}", exc_info=True)
            return False

    async def get_or_create_default(self) -> Dict:
        """
        Load settings from database or create defaults from environment variables.

        Returns:
            Dictionary with upload settings
        """
        # Try to load from database
        settings = self.get_settings()

        if settings:
            logger.info("Loaded upload settings from database")
            return settings

        # No settings in DB: initialize from environment variables
        logger.info(
            "No upload settings in database, initializing from environment variables"
        )

        default_extensions = config.ALLOWED_FILE_EXTENSIONS
        default_size = config.UPLOAD_MAX_FILE_SIZE_MB

        # Save defaults to database
        success = await self.save_settings(
            allowed_extensions=default_extensions,
            max_file_size_mb=default_size,
            updated_by="system",
        )

        if not success:
            logger.warning("Failed to save default settings to database")

        # Return the defaults
        return {
            "allowed_extensions": json.dumps(default_extensions),
            "max_file_size_mb": default_size,
            "updated_at": None,
            "updated_by": "system",
        }
