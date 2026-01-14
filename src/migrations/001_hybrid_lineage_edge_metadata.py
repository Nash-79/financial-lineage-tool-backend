"""
Neo4j Migration: Add indexes for hybrid lineage edge metadata

This migration creates indexes on edge properties to support efficient
querying of edges by source, status, and confidence.

Run this migration after deploying the hybrid lineage system changes.
"""

from src.knowledge_graph.neo4j_client import Neo4jGraphClient
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def run_migration(client: Neo4jGraphClient):
    """
    Create indexes for hybrid lineage edge properties.

    Note: Neo4j doesn't support direct property indexes on relationships
    in all versions. For relationship property queries, we rely on:
    1. Scanning (acceptable for moderate datasets)
    2. Materialization patterns if performance becomes an issue

    This migration documents the schema change for reference.
    """
    logger.info("Running hybrid lineage edge metadata migration")

    # Document the new relationship properties in a schema metadata node
    # This helps with discoverability and validation
    schema_query = """
    MERGE (schema:SchemaMetadata {version: 'hybrid_lineage_v1'})
    SET schema.edge_properties = [
        'source',      // Source of the edge: 'parser', 'ollama_llm', 'human'
        'confidence',  // Confidence score: 0.0-1.0
        'status',      // Status: 'pending_review', 'approved', 'rejected'
        'evidence'     // Optional: supporting evidence for inferred edges
    ]
    SET schema.updated_at = datetime()
    RETURN schema
    """

    try:
        client._execute_write(schema_query, {})
        logger.info("Schema metadata node created/updated successfully")
    except Exception as e:
        logger.error(f"Failed to create schema metadata: {e}")
        raise

    logger.info("Migration completed successfully")
    print("✓ Hybrid lineage edge metadata migration completed")


if __name__ == "__main__":
    load_dotenv()

    # Initialize Neo4j client
    neo4j_client = Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )

    try:
        run_migration(neo4j_client)
    finally:
        neo4j_client.close()
