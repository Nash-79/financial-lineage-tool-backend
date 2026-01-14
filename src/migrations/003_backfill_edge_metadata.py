"""
Migration 003: Backfill Legacy Edge Metadata

This migration sets default hybrid lineage metadata on existing edges
that were created before the hybrid lineage system was implemented.

Idempotent: Only sets values where properties are missing (uses COALESCE).
Safe to run multiple times.
"""

import logging

logger = logging.getLogger(__name__)


def run_migration(neo4j_client):
    """
    Backfill legacy edges with default metadata properties.

    Sets:
    - source: "parser" (for edges created by deterministic parser)
    - status: "approved" (legacy edges are considered approved)
    - confidence: 1.0 (deterministic edges have full confidence)

    Only sets properties where they are currently missing (NULL).
    """
    logger.info("Running migration 003: Backfill Legacy Edge Metadata")

    # Query to update all relationships missing hybrid metadata
    # Uses COALESCE to only set if property is NULL
    backfill_query = """
    MATCH ()-[r]->()
    WHERE r.source IS NULL OR r.status IS NULL OR r.confidence IS NULL
    SET r.source = COALESCE(r.source, 'parser'),
        r.status = COALESCE(r.status, 'approved'),
        r.confidence = COALESCE(r.confidence, 1.0)
    RETURN count(r) as updated_count
    """

    try:
        result = neo4j_client._execute_write(backfill_query)
        updated_count = result[0]["updated_count"] if result else 0
        logger.info(f"Backfilled {updated_count} legacy edges with default metadata")
        return updated_count
    except Exception as e:
        logger.error(f"Failed to backfill legacy edges: {e}")
        raise


if __name__ == "__main__":
    # Standalone execution
    import sys

    sys.path.insert(0, ".")

    from src.knowledge_graph.neo4j_client import Neo4jGraphClient
    from src.api.config import config

    print("[*] Running migration: 003_backfill_edge_metadata")
    print(f"[*] Connecting to Neo4j at {config.NEO4J_URI}...")

    client = Neo4jGraphClient(
        uri=config.NEO4J_URI,
        username=config.NEO4J_USERNAME,
        password=config.NEO4J_PASSWORD,
    )

    try:
        updated = run_migration(client)
        print(f"[+] Migration complete: {updated} edges updated")
    finally:
        client.close()
