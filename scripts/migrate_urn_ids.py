"""Backfill URN identifiers for legacy Neo4j nodes."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.utils.urn import generate_urn, is_valid_urn, normalize_asset_path


def _resolve_asset(record: dict) -> str:
    for key in ("path", "file_path", "source_file", "name", "id"):
        value = record.get(key)
        if value:
            return normalize_asset_path(str(value))
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill URN IDs for legacy nodes.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print changes without writing"
    )
    args = parser.parse_args()

    load_dotenv()

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not uri or not username or not password:
        raise SystemExit("NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD must be set")

    client = Neo4jGraphClient(
        uri=uri, username=username, password=password, database=database
    )

    records = client._execute_query(
        """
        MATCH (n)
        WHERE NOT n.id STARTS WITH 'urn:li:'
        RETURN id(n) AS internal_id, n.id AS id, labels(n) AS labels,
               n.project_id AS project_id, n.name AS name,
               n.path AS path, n.file_path AS file_path, n.source_file AS source_file
        """
    )

    updates = 0
    for record in records:
        legacy_id = record.get("id")
        if not legacy_id or is_valid_urn(legacy_id):
            continue
        labels = record.get("labels") or ["Node"]
        label = labels[0] if labels else "Node"
        project_id = record.get("project_id") or "default"
        asset_path = _resolve_asset(record)
        new_id = generate_urn(label, project_id, asset_path)

        if args.dry_run:
            print(f"[dry-run] {legacy_id} -> {new_id}")
            updates += 1
            continue

        client._execute_write(
            """
            MATCH (n) WHERE id(n) = $internal_id
            SET n.legacy_id = $legacy_id, n.id = $new_id
            RETURN n.id as id
            """,
            {
                "internal_id": record.get("internal_id"),
                "legacy_id": legacy_id,
                "new_id": new_id,
            },
        )
        updates += 1

    client.close()
    print(f"Updated {updates} nodes")


if __name__ == "__main__":
    main()
