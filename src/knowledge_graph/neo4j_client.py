"""
Neo4j Graph Database Client for Knowledge Graph Operations.

This module provides a high-level interface for interacting with the
lineage knowledge graph stored in Neo4j.
"""

import os
import time
import logging
from typing import Optional, Any, List, Dict
from dataclasses import dataclass
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError, TransientError

logger = logging.getLogger(__name__)

# Import DataPathManager for new hierarchical structure
try:
    from ..utils.data_paths import DataPathManager

    HAS_DATA_PATH_MANAGER = True
except ImportError:
    HAS_DATA_PATH_MANAGER = False


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str
    username: str
    password: str
    database: str = "neo4j"


class Neo4jGraphClient:
    """
    Client for Neo4j graph database operations.

    Provides methods for:
    - Entity CRUD operations
    - Relationship management
    - Lineage traversal queries
    - Graph analytics
    """

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """
        Initialize the Neo4j client.

        Args:
            uri: Neo4j connection URI (e.g., neo4j+s://xxx.databases.neo4j.io)
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: neo4j)
        """
        self.uri = uri
        self.username = username
        self.database = database

        try:
            self.driver: Driver = GraphDatabase.driver(
                uri, auth=(username, password), max_connection_lifetime=3600
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            print(f"[+] Connected to Neo4j at {uri}")
        except (ServiceUnavailable, AuthError) as e:
            print(f"[!] Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            print("[*] Neo4j connection closed")

    def _execute_query(self, query: str, parameters: dict = None) -> list:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def _execute_write(self, query: str, parameters: dict = None) -> list:
        """
        Execute a write transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records
        """
        with self.driver.session(database=self.database) as session:
            result = session.execute_write(
                lambda tx: list(tx.run(query, parameters or {}))
            )
            return [record.data() for record in result]

    # ==================== Entity Operations ====================

    def add_entity(
        self, entity_id: str, entity_type: str, name: str, **properties
    ) -> str:
        """
        Add a node to the graph.

        Args:
            entity_id: Unique entity identifier
            entity_type: Node label/type
            name: Entity name
            **properties: Additional properties

        Returns:
            The entity ID
        """
        query = f"""
        MERGE (n:{entity_type} {{id: $entity_id}})
        SET n.name = $name
        SET n += $properties
        RETURN n.id as id
        """

        self._execute_write(
            query, {"entity_id": entity_id, "name": name, "properties": properties}
        )

        return entity_id

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """
        Get a node by ID.

        Args:
            entity_id: Entity identifier

        Returns:
            Entity data as dict, or None if not found
        """
        query = """
        MATCH (n {id: $entity_id})
        RETURN n, labels(n) as labels
        """

        results = self._execute_query(query, {"entity_id": entity_id})

        if not results:
            return None

        node_data = results[0]["n"]
        labels = results[0]["labels"]

        return {
            "id": entity_id,
            "entity_type": labels[0] if labels else "Unknown",
            **node_data,
        }

    def find_by_name(self, name_pattern: str, project_id: str = None) -> list[dict]:
        """
        Find nodes by name pattern (case-insensitive contains).

        Args:
            name_pattern: Name pattern to search
            project_id: Filter by project ID (optional)

        Returns:
            List of matching entities
        """
        where_params = ["toLower(n.name) CONTAINS toLower($pattern)"]
        if project_id:
            where_params.append("n.project_id = $project_id")
            
        where_clause = " AND ".join(where_params)

        query = f"""
        MATCH (n)
        WHERE {where_clause}
        RETURN n, labels(n) as labels
        LIMIT 100
        """

        results = self._execute_query(query, {"pattern": name_pattern, "project_id": project_id})

        entities = []
        for record in results:
            node_data = record["n"]
            labels = record["labels"]
            entities.append(
                {
                    "id": node_data.get("id"),
                    "entity_type": labels[0] if labels else "Unknown",
                    **node_data,
                }
            )

        return entities

    def find_by_names(self, names: List[str], project_id: str = None, limit: int = 50) -> list[dict]:
        """
        Find nodes by multiple name patterns in a single query (batch operation).

        This is more efficient than calling find_by_name() multiple times as it
        executes a single Cypher query with an IN clause.

        Args:
            names: List of name patterns to search (case-insensitive contains)
            project_id: Filter by project ID (optional)
            limit: Maximum results to return (default: 50)

        Returns:
            List of matching entities (deduplicated)
        """
        if not names:
            return []

        # Filter out short words and normalize
        filtered_names = [n.strip().lower() for n in names if len(n.strip()) > 2]
        if not filtered_names:
            return []

        # Build WHERE clause
        where_params = ["ANY(pattern IN $patterns WHERE toLower(n.name) CONTAINS pattern)"]
        if project_id:
            where_params.append("n.project_id = $project_id")

        where_clause = " AND ".join(where_params)

        query = f"""
        MATCH (n)
        WHERE {where_clause}
        RETURN DISTINCT n, labels(n) as labels
        LIMIT $limit
        """

        results = self._execute_query(
            query,
            {"patterns": filtered_names, "project_id": project_id, "limit": limit}
        )

        entities = []
        seen_ids = set()
        for record in results:
            node_data = record["n"]
            node_id = node_data.get("id")
            if node_id and node_id not in seen_ids:
                seen_ids.add(node_id)
                labels = record["labels"]
                entities.append(
                    {
                        "id": node_id,
                        "entity_type": labels[0] if labels else "Unknown",
                        **node_data,
                    }
                )

        return entities

    # ==================== Relationship Operations ====================

    def add_relationship(
        self, source_id: str, target_id: str, relationship_type: str, **properties
    ):
        """
        Add an edge to the graph.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            relationship_type: Relationship type
            **properties: Relationship properties
        """
        query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:{relationship_type}]->(target)
        SET r += $properties
        RETURN r
        """

        self._execute_write(
            query,
            {"source_id": source_id, "target_id": target_id, "properties": properties},
        )

    # ==================== Batch Operations ====================

    def batch_create_entities(
        self,
        entities: List[Dict[str, Any]],
        batch_size: int = 100,
        max_retries: int = 5,
    ) -> int:
        """
        Create multiple entities in batches using UNWIND pattern.

        Args:
            entities: List of entity dictionaries with keys:
                - id: Entity ID (required)
                - entity_type: Node label (required)
                - name: Entity name (required)
                - additional properties as key-value pairs
            batch_size: Maximum entities per batch (default: 100)
            max_retries: Maximum retry attempts on transient errors

        Returns:
            Number of entities created

        Example:
            entities = [
                {"id": "t1", "entity_type": "Table", "name": "Users", "schema": "dbo"},
                {"id": "t2", "entity_type": "Table", "name": "Orders", "schema": "dbo"}
            ]
            client.batch_create_entities(entities)
        """
        if not entities:
            return 0

        total_created = 0

        # Split into batches
        batches = self._split_into_batches(entities, batch_size)

        for batch_num, batch in enumerate(batches, 1):
            logger.debug(
                f"Processing entity batch {batch_num}/{len(batches)} ({len(batch)} entities)"
            )

            # Extract entity type from first entity (assume homogeneous batches for now)
            # For heterogeneous batches, we'd need a different approach
            entity_type = batch[0].get("entity_type", "Node")

            # Prepare batch data (exclude entity_type from properties)
            batch_data = []
            for entity in batch:
                props = {k: v for k, v in entity.items() if k not in ["entity_type"]}
                batch_data.append(props)

            query = f"""
            UNWIND $entities AS entity
            MERGE (n:{entity_type} {{id: entity.id}})
            SET n += entity
            RETURN count(n) as created
            """

            try:
                result = self._execute_write_with_retry(
                    query,
                    {"entities": batch_data},
                    max_retries=max_retries,
                    batch_size=len(batch),
                )
                created = result[0]["created"] if result else len(batch)
                total_created += created
                logger.debug(f"Created {created} entities in batch {batch_num}")

            except Exception as e:
                logger.error(
                    f"Failed to create entity batch {batch_num} after retries: {e}"
                )
                # Try partial failure recovery
                partial_created = self._handle_partial_failure(
                    query, batch_data, batch_size, max_retries, "entities"
                )
                total_created += partial_created

        logger.info(
            f"Batch entity creation complete: {total_created}/{len(entities)} entities created"
        )
        return total_created

    def batch_create_relationships(
        self,
        relationships: List[Dict[str, Any]],
        batch_size: int = 100,
        max_retries: int = 5,
    ) -> int:
        """
        Create multiple relationships in batches using UNWIND pattern.

        Args:
            relationships: List of relationship dictionaries with keys:
                - source_id: Source node ID (required)
                - target_id: Target node ID (required)
                - relationship_type: Relationship type (required)
                - additional properties as key-value pairs
            batch_size: Maximum relationships per batch (default: 100)
            max_retries: Maximum retry attempts on transient errors

        Returns:
            Number of relationships created

        Example:
            relationships = [
                {"source_id": "t1", "target_id": "c1", "relationship_type": "CONTAINS"},
                {"source_id": "t2", "target_id": "c2", "relationship_type": "CONTAINS"}
            ]
            client.batch_create_relationships(relationships)
        """
        if not relationships:
            return 0

        total_created = 0

        # Split into batches
        batches = self._split_into_batches(relationships, batch_size)

        for batch_num, batch in enumerate(batches, 1):
            logger.debug(
                f"Processing relationship batch {batch_num}/{len(batches)} ({len(batch)} relationships)"
            )

            # Extract relationship type from first relationship
            rel_type = batch[0].get("relationship_type", "RELATED_TO")

            # Prepare batch data
            batch_data = []
            for rel in batch:
                props = {k: v for k, v in rel.items() if k not in ["relationship_type"]}
                batch_data.append(props)

            query = f"""
            UNWIND $relationships AS rel
            MATCH (source {{id: rel.source_id}})
            MATCH (target {{id: rel.target_id}})
            MERGE (source)-[r:{rel_type}]->(target)
            SET r += rel
            RETURN count(r) as created
            """

            try:
                result = self._execute_write_with_retry(
                    query,
                    {"relationships": batch_data},
                    max_retries=max_retries,
                    batch_size=len(batch),
                )
                created = result[0]["created"] if result else len(batch)
                total_created += created
                logger.debug(f"Created {created} relationships in batch {batch_num}")

            except Exception as e:
                logger.error(
                    f"Failed to create relationship batch {batch_num} after retries: {e}"
                )
                # Try partial failure recovery
                partial_created = self._handle_partial_failure(
                    query, batch_data, batch_size, max_retries, "relationships"
                )
                total_created += partial_created

        logger.info(
            f"Batch relationship creation complete: {total_created}/{len(relationships)} relationships created"
        )
        return total_created

    def _split_into_batches(self, items: List[Any], batch_size: int) -> List[List[Any]]:
        """Split list into batches of specified size."""
        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i : i + batch_size])
        return batches

    def _execute_write_with_retry(
        self,
        query: str,
        parameters: Dict[str, Any],
        max_retries: int = 5,
        batch_size: int = None,
    ) -> list:
        """
        Execute write transaction with exponential backoff retry on transient errors.

        Args:
            query: Cypher query
            parameters: Query parameters
            max_retries: Maximum retry attempts
            batch_size: Batch size (for logging)

        Returns:
            Query results

        Raises:
            Exception: If all retry attempts fail
        """
        retry_delays = [1, 2, 4, 8, 16]  # Exponential backoff in seconds

        for attempt in range(max_retries):
            try:
                with self.driver.session(database=self.database) as session:
                    result = session.execute_write(
                        lambda tx: list(tx.run(query, parameters))
                    )
                    return [record.data() for record in result]

            except TransientError as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                    logger.warning(
                        f"Transient error on attempt {attempt + 1}/{max_retries} "
                        f"(batch_size={batch_size}): {e}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} retry attempts failed")
                    raise

            except Exception as e:
                # Non-transient error - don't retry
                logger.error(f"Non-transient error during batch write: {e}")
                raise

    def _handle_partial_failure(
        self,
        query: str,
        batch_data: List[Dict],
        original_batch_size: int,
        max_retries: int,
        param_name: str,
    ) -> int:
        """
        Handle partial batch failure by splitting into smaller batches.

        Implements progressive batch size reduction: 100 → 50 → 10 → 1

        Args:
            query: Cypher query
            batch_data: Batch data that failed
            original_batch_size: Original batch size
            max_retries: Maximum retry attempts
            param_name: Parameter name in query ("entities" or "relationships")

        Returns:
            Number of items successfully processed
        """
        # Progressive batch size reduction
        reduced_sizes = [
            original_batch_size // 2,  # 50
            original_batch_size // 10,  # 10
            1,  # Individual items
        ]

        for reduced_size in reduced_sizes:
            if reduced_size < 1:
                continue

            logger.info(f"Retrying with reduced batch size: {reduced_size}")

            try:
                total_processed = 0
                sub_batches = self._split_into_batches(batch_data, reduced_size)

                for sub_batch in sub_batches:
                    try:
                        result = self._execute_write_with_retry(
                            query,
                            {param_name: sub_batch},
                            max_retries=max_retries,
                            batch_size=len(sub_batch),
                        )
                        processed = (
                            result[0].get("created", len(sub_batch))
                            if result
                            else len(sub_batch)
                        )
                        total_processed += processed

                    except Exception as e:
                        logger.error(f"Sub-batch failed (size={len(sub_batch)}): {e}")
                        # Log failed items
                        self._log_failed_items(sub_batch, str(e))

                if total_processed > 0:
                    logger.info(
                        f"Partial recovery successful: {total_processed}/{len(batch_data)} items processed"
                    )
                    return total_processed

            except Exception as e:
                logger.error(
                    f"Partial failure recovery failed at batch size {reduced_size}: {e}"
                )
                continue

        # All recovery attempts failed
        logger.error(
            f"All partial recovery attempts failed. Logging {len(batch_data)} failed items."
        )
        self._log_failed_items(batch_data, "All retry attempts exhausted")
        return 0

    def _log_failed_items(
        self, items: List[Dict], error_message: str, database_name: str = "default"
    ):
        """
        Log failed items to failed_ingestion.jsonl.

        Args:
            items: Failed items
            error_message: Error description
            database_name: Database name for new hierarchical structure
        """
        import json
        from datetime import datetime
        from pathlib import Path

        # Use new hierarchical structure if available
        if HAS_DATA_PATH_MANAGER:
            paths = DataPathManager(data_root="./data", database_name=database_name)
            log_file = paths.metadata_path("failed_ingestion.jsonl")
        else:
            # Fallback to old structure
            log_file = Path("data/failed_ingestion.jsonl")
            log_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(log_file, "a") as f:
                for item in items:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "error": error_message,
                        "database": database_name,
                        "item": item,
                    }
                    f.write(json.dumps(log_entry) + "\n")

            logger.info(f"Logged {len(items)} failed items to {log_file}")

        except Exception as e:
            logger.error(f"Failed to log failed items: {e}")

    # ==================== Lineage Queries ====================

    def get_upstream(
        self,
        entity_id: str,
        max_depth: int = 10,
        project_id: str = None,
        repo_ids: List[str] = None,
    ) -> list[dict]:
        """
        Get all upstream (incoming) relationships.

        Args:
            entity_id: Starting entity ID
            max_depth: Maximum traversal depth
            project_id: Filter by project ID (optional)
            repo_ids: Filter by repository IDs (optional)

        Returns:
            List of upstream relationships
        """
        # Build where clause for filtering
        where_clauses = ["(source.project_id = $project_id OR $project_id IS NULL)"]
        if repo_ids:
            where_clauses.append("(source.repository_id IN $repo_ids)")
        
        where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = """
        MATCH path = (source)-[r*1..{max_depth}]->(target {{id: $entity_id}})
        {where_stmt}
        WITH source, target, relationships(path) as rels, nodes(path) as nodes
        UNWIND range(0, size(rels)-1) as idx
        WITH nodes[idx] as src, rels[idx] as rel, nodes[idx+1] as tgt, idx
        RETURN
            src.id as source,
            type(rel) as relationship,
            tgt.id as target,
            properties(src) as source_data,
            idx as depth
        LIMIT 100
        """.format(
            max_depth=max_depth,
            where_stmt=where_stmt
        )

        return self._execute_query(
            query,
            {
                "entity_id": entity_id,
                "project_id": project_id,
                "repo_ids": repo_ids
            }
        )

    def get_downstream(
        self,
        entity_id: str,
        max_depth: int = 10,
        project_id: str = None,
        repo_ids: List[str] = None,
    ) -> list[dict]:
        """
        Get all downstream (outgoing) relationships.

        Args:
            entity_id: Starting entity ID
            max_depth: Maximum traversal depth
            project_id: Filter by project ID (optional)
            repo_ids: Filter by repository IDs (optional)

        Returns:
            List of downstream relationships
        """
        # Build where clause for filtering targets
        where_clauses = ["(target.project_id = $project_id OR $project_id IS NULL)"]
        if repo_ids:
            where_clauses.append("(target.repository_id IN $repo_ids)")
        
        where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = """
        MATCH path = (source {{id: $entity_id}})-[r*1..{max_depth}]->(target)
        {where_stmt}
        WITH source, target, relationships(path) as rels, nodes(path) as nodes
        UNWIND range(0, size(rels)-1) as idx
        WITH nodes[idx] as src, rels[idx] as rel, nodes[idx+1] as tgt, idx
        RETURN
            src.id as source,
            type(rel) as relationship,
            tgt.id as target,
            properties(tgt) as target_data,
            idx as depth
        LIMIT 100
        """.format(
            max_depth=max_depth,
            where_stmt=where_stmt
        )

        return self._execute_query(
            query, 
            {
                "entity_id": entity_id,
                "project_id": project_id,
                "repo_ids": repo_ids
            }
        )

    def get_path(self, source_id: str, target_id: str) -> list[str]:
        """
        Find shortest path between two nodes.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID

        Returns:
            List of node IDs in the path
        """
        query = """
        MATCH path = shortestPath(
            (source {id: $source_id})-[*]-(target {id: $target_id})
        )
        RETURN [node in nodes(path) | node.id] as path
        """

        results = self._execute_query(
            query, {"source_id": source_id, "target_id": target_id}
        )

        return results[0]["path"] if results else []

    # ==================== Graph Analytics ====================

    def get_stats(self) -> dict:
        """
        Get graph statistics.

        Returns:
            Dictionary with node/edge counts and type distributions
        """
        # Get node count
        node_count_query = "MATCH (n) RETURN count(n) as count"
        node_count = self._execute_query(node_count_query)[0]["count"]

        # Get edge count
        edge_count_query = "MATCH ()-[r]->() RETURN count(r) as count"
        edge_count = self._execute_query(edge_count_query)[0]["count"]

        # Get node types
        node_types_query = """
        MATCH (n)
        UNWIND labels(n) as label
        RETURN label, count(*) as count
        """
        node_types_results = self._execute_query(node_types_query)
        node_types = {r["label"]: r["count"] for r in node_types_results}

        # Get relationship types
        rel_types_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(*) as count
        """
        rel_types_results = self._execute_query(rel_types_query)
        relationship_types = {r["type"]: r["count"] for r in rel_types_results}

        return {
            "nodes": node_count,
            "edges": edge_count,
            "node_types": node_types,
            "relationship_types": relationship_types,
        }

    def clear_graph(self):
        """
        Clear all nodes and relationships from the graph.
        WARNING: This will delete all data!
        """
        query = "MATCH (n) DETACH DELETE n"
        self._execute_write(query)
        print("[!] Graph cleared")

    def create_indexes(self):
        """
        Create recommended indexes for performance.
        """
        indexes = [
            "CREATE INDEX entity_id IF NOT EXISTS FOR (n:Table) ON (n.id)",
            "CREATE INDEX entity_id IF NOT EXISTS FOR (n:Column) ON (n.id)",
            "CREATE INDEX entity_id IF NOT EXISTS FOR (n:View) ON (n.id)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Table) ON (n.name)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Column) ON (n.name)",
        ]

        for index_query in indexes:
            try:
                self._execute_write(index_query)
                print(f"[+] Created index: {index_query[:50]}...")
            except Exception as e:
                print(f"[i] Index may already exist: {e}")


# ==================== Helper Functions ====================


def create_neo4j_client_from_env() -> Neo4jGraphClient:
    """
    Create Neo4j client from environment variables.

    Expected environment variables:
    - NEO4J_URI
    - NEO4J_USERNAME
    - NEO4J_PASSWORD
    - NEO4J_DATABASE (optional, defaults to 'neo4j')

    Returns:
        Initialized Neo4j client
    """
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not all([uri, username, password]):
        raise ValueError(
            "Missing required environment variables: "
            "NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD"
        )

    return Neo4jGraphClient(
        uri=uri, username=username, password=password, database=database
    )
