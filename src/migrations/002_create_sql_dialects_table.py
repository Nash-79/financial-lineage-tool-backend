"""
Migration: Create SQL Dialects Table

Creates the sql_dialects table in DuckDB and seeds it with default values
from the configuration file.
"""

import sys
import duckdb
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.config import config
from src.config.sql_dialects import SQL_DIALECTS


def migrate():
    """Run the migration."""
    print(f"[*] Running migration: 002_create_sql_dialects_table")
    print(f"[*] Connecting to DuckDB at {config.DUCKDB_PATH}...")

    con = duckdb.connect(config.DUCKDB_PATH)

    try:
        # Create table
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS sql_dialects (
                id VARCHAR PRIMARY KEY,
                display_name VARCHAR NOT NULL,
                sqlglot_read_key VARCHAR NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                is_default BOOLEAN DEFAULT FALSE,
                description VARCHAR
            )
        """
        )
        print("[+] Created table sql_dialects")

        # Seed data
        # Check if empty
        count = con.execute("SELECT COUNT(*) FROM sql_dialects").fetchone()[0]

        if count == 0:
            print("[*] Seeding default dialects...")
            insert_query = """
                INSERT INTO sql_dialects (id, display_name, sqlglot_read_key, enabled, is_default, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """

            for d in SQL_DIALECTS.values():
                con.execute(
                    insert_query,
                    (
                        d["id"],
                        d["display_name"],
                        d["sqlglot_read_key"],
                        d["enabled"],
                        d["is_default"],
                        d["description"],
                    ),
                )
            print(f"[+] Seeded {len(SQL_DIALECTS)} dialects")
        else:
            print("[i] Table already has data, skipping seed")

    except Exception as e:
        print(f"[!] Migration failed: {e}")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    migrate()
