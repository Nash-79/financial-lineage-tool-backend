"""
Export utilities for Knowledge Graph and Embeddings.
"""

import json
import os
from typing import List, Dict, Any
from datetime import datetime
import httpx
from dotenv import load_dotenv

from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.storage.artifact_manager import ArtifactManager

load_dotenv()

# --- Graph Exports ---


def export_graph_to_json(
    output_file: str = "data/graph_export.json",
    run_id: str = None,
    project_id: str = None,
) -> Dict[str, Any]:
    """
    Export the entire Neo4j graph to JSON format.

    Args:
        output_file: Output file path (used if run_id not provided)
        run_id: Optional run ID to save export in run's graph_export directory
        project_id: Optional project ID (required if run_id provided)

    Returns:
        Dictionary containing the exported graph data
    """
    print("[*] Connecting to Neo4j...")
    client = Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    print("[+] Connected to Neo4j")

    try:
        # Get all nodes
        print("[*] Fetching all nodes...")
        nodes_result = client._execute_query(
            """
        MATCH (n)
        RETURN n.id as id, labels(n) as labels, properties(n) as properties
        """
        )

        nodes = [
            {"id": r["id"], "labels": r["labels"], "properties": r["properties"]}
            for r in nodes_result
        ]
        print(f"[+] Fetched {len(nodes)} nodes")

        # Get all relationships
        print("[*] Fetching all relationships...")
        rels_result = client._execute_query(
            """
        MATCH (source)-[r]->(target)
        RETURN source.id as source_id, target.id as target_id, type(r) as type, properties(r) as properties
        """
        )

        relationships = [
            {
                "source": r["source_id"],
                "target": r["target_id"],
                "type": r["type"],
                "properties": r["properties"],
            }
            for r in rels_result
        ]
        print(f"[+] Fetched {len(relationships)} relationships")

        stats = client.get_stats()

        graph_export = {
            "metadata": {
                "export_timestamp": datetime.utcnow().isoformat(),
                "database": os.getenv("NEO4J_DATABASE", "neo4j"),
                "statistics": stats,
                "run_id": run_id,
                "project_id": project_id,
            },
            "nodes": nodes,
            "relationships": relationships,
        }

        # Determine output path
        if run_id:
            artifact_manager = ArtifactManager()
            export_dir = artifact_manager.get_artifact_path(run_id, "graph_export")
            if export_dir:
                output_file = str(export_dir / "graph_export.json")
            else:
                print(
                    f"[!] Warning: Could not resolve run directory for run_id={run_id}, using default path"
                )

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(f"[*] Writing to {output_file}...")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(graph_export, f, indent=2, ensure_ascii=False)

        print(f"[+] Graph exported to {output_file}")
        return graph_export
    finally:
        client.close()


def export_graph_for_visualization(
    output_file: str = "data/graph_viz.json", run_id: str = None, project_id: str = None
) -> Dict[str, Any]:
    """
    Export graph in a format optimized for D3.js.

    Args:
        output_file: Output file path (used if run_id not provided)
        run_id: Optional run ID to save export in run's graph_export directory
        project_id: Optional project ID (required if run_id provided)

    Returns:
        Dictionary containing the visualization data
    """
    print("[*] Connecting to Neo4j...")
    client = Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    print("[+] Connected to Neo4j")

    try:
        nodes_result = client._execute_query(
            """
        MATCH (n)
        RETURN n.id as id, labels(n)[0] as group, n.name as name, properties(n) as properties
        """
        )

        node_index, viz_nodes = {}, []
        for idx, r in enumerate(nodes_result):
            node_index[r["id"]] = idx
            viz_nodes.append(
                {
                    "id": r["id"],
                    "name": r["name"] or r["id"],
                    "group": r["group"],
                    "properties": r["properties"],
                }
            )

        rels_result = client._execute_query(
            """
        MATCH (source)-[r]->(target)
        RETURN source.id as source_id, target.id as target_id, type(r) as type, properties(r) as properties
        """
        )

        viz_links = []
        for r in rels_result:
            if r["source_id"] in node_index and r["target_id"] in node_index:
                viz_links.append(
                    {
                        "source": node_index[r["source_id"]],
                        "target": node_index[r["target_id"]],
                        "type": r["type"],
                        "properties": r["properties"],
                    }
                )

        viz_export = {
            "nodes": viz_nodes,
            "links": viz_links,
            "metadata": {
                "run_id": run_id,
                "project_id": project_id,
                "export_timestamp": datetime.utcnow().isoformat(),
            },
        }

        # Determine output path
        if run_id:
            artifact_manager = ArtifactManager()
            export_dir = artifact_manager.get_artifact_path(run_id, "graph_export")
            if export_dir:
                output_file = str(export_dir / "graph_viz.json")
            else:
                print(
                    f"[!] Warning: Could not resolve run directory for run_id={run_id}, using default path"
                )

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(f"[*] Writing to {output_file}...")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(viz_export, f, indent=2, ensure_ascii=False)

        print(f"[+] Viz data exported to {output_file}")
        return viz_export
    finally:
        client.close()


def export_cypher_queries(
    output_file: str = "data/cypher_queries.json",
) -> Dict[str, Any]:
    """
    Export common Cypher queries.
    """
    queries = {
        "get_all_tables": {
            "description": "Get all table nodes",
            "cypher": "MATCH (n:Table) RETURN n",
        },
        "get_all_columns": {
            "description": "Get all column nodes",
            "cypher": "MATCH (n:Column) RETURN n",
        },
        "get_table_columns": {
            "description": "Get columns for a specific table",
            "cypher": "MATCH (t:Table {id: $table_id})-[:CONTAINS]->(c:Column) RETURN t, c",
            "parameters": {"table_id": "table_identifier"},
        },
        "get_upstream_lineage": {
            "description": "Get upstream lineage for an entity",
            "cypher": "MATCH path = (source)-[:DERIVES_FROM|TRANSFORMS_TO*1..5]->(target {id: $entity_id}) RETURN path",
            "parameters": {"entity_id": "entity_identifier"},
        },
        "get_downstream_lineage": {
            "description": "Get downstream lineage for an entity",
            "cypher": "MATCH path = (source {id: $entity_id})-[:DERIVES_FROM|TRANSFORMS_TO*1..5]->(target) RETURN path",
            "parameters": {"entity_id": "entity_identifier"},
        },
        "find_entity_by_name": {
            "description": "Find entities by name pattern",
            "cypher": "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($name_pattern) RETURN n",
            "parameters": {"name_pattern": "search_term"},
        },
        "get_graph_stats": {
            "description": "Get graph statistics",
            "cypher": "MATCH (n) RETURN labels(n) as label, count(*) as count",
        },
        "get_relationship_stats": {
            "description": "Get relationship type counts",
            "cypher": "MATCH ()-[r]->() RETURN type(r) as type, count(*) as count",
        },
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(queries, f, indent=2, ensure_ascii=False)

    return queries


# --- Embedding Exports ---


class EmbeddingExporter:
    """Generate and export embeddings to JSON."""

    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate_embedding(self, text: str) -> List[float]:
        response = await self.client.post(
            f"{self.ollama_host}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
        )
        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")
        return response.json()["embedding"]

    async def export_text_embeddings(
        self, texts: List[str], output_file: str = "data/embeddings_export.json"
    ):
        print(f"[*] Generating embeddings for {len(texts)} texts...")
        embeddings_data = []
        for idx, text in enumerate(texts):
            try:
                emb = await self.generate_embedding(text)
                embeddings_data.append(
                    {
                        "id": idx,
                        "text": text,
                        "embedding": emb,
                        "embedding_dimension": len(emb),
                        "model": self.embedding_model,
                    }
                )
            except Exception as e:
                embeddings_data.append({"id": idx, "text": text, "error": str(e)})

        self._write_export(embeddings_data, output_file, len(texts))

    async def export_sql_embeddings(
        self, sql_file: str, output_file: str = "data/sql_embeddings.json"
    ):
        print(f"[*] Reading SQL file: {sql_file}")
        with open(sql_file, "r", encoding="utf-8") as f:
            content = f.read()
        statements = [s.strip() for s in content.split(";") if s.strip()]

        embeddings_data = []
        for idx, stmt in enumerate(statements):
            try:
                emb = await self.generate_embedding(stmt)
                embeddings_data.append(
                    {
                        "id": idx,
                        "sql": stmt,
                        "embedding": emb,
                        "embedding_dimension": len(emb),
                        "model": self.embedding_model,
                    }
                )
            except Exception as e:
                embeddings_data.append({"id": idx, "sql": stmt[:100], "error": str(e)})

        self._write_export(embeddings_data, output_file, len(statements))

    async def export_entity_embeddings(
        self, output_file: str = "data/entity_embeddings.json"
    ):
        print("[*] Connecting to Neo4j...")
        client = Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )
        try:
            entities = client._execute_query(
                """
            MATCH (n) RETURN n.id as id, n.name as name, labels(n)[0] as type, properties(n) as properties
            """
            )
            print(f"[+] Found {len(entities)} entities")

            embeddings_data = []
            for ent in entities:
                text = f"{ent['type']}: {ent['name'] or ent['id']}"
                if ent["properties"]:
                    props = ", ".join(
                        [
                            f"{k}={v}"
                            for k, v in ent["properties"].items()
                            if k not in ["id", "name"]
                        ]
                    )
                    if props:
                        text += f" ({props})"

                try:
                    emb = await self.generate_embedding(text)
                    embeddings_data.append(
                        {
                            "entity_id": ent["id"],
                            "entity_name": ent["name"],
                            "text_representation": text,
                            "embedding": emb,
                            "embedding_dimension": len(emb),
                            "model": self.embedding_model,
                        }
                    )
                except Exception as e:
                    embeddings_data.append({"entity_id": ent["id"], "error": str(e)})

            self._write_export(embeddings_data, output_file, len(entities))
        finally:
            client.close()

    def _write_export(self, data: List[Dict], output_file: str, total_count: int):
        export_data = {
            "metadata": {
                "total_items": total_count,
                "successful": len([e for e in data if "embedding" in e]),
                "failed": len([e for e in data if "error" in e]),
                "model": self.embedding_model,
            },
            "embeddings": data,
        }
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(f"[*] Writing to {output_file}...")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"[+] Embeddings exported to {output_file}")

    async def close(self):
        await self.client.aclose()
