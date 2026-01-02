"""
Diagnostic utilities for the Knowledge Graph.
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from src.knowledge_graph.neo4j_client import Neo4jGraphClient

load_dotenv()


class GraphInspector:
    """Methods to inspect and report on Graph state."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.client = None

    def connect(self):
        print(f"[*] Connecting to Neo4j at {self.uri}...")
        try:
            self.client = Neo4jGraphClient(
                uri=self.uri,
                username=self.username,
                password=self.password,
                database=self.database,
            )
            print("[+] Connected!\n")
            return True
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return False

    def close(self):
        if self.client:
            self.client.close()

    def print_section(self, title):
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def run_diagnostics(self):
        """Run full interactive diagnostics."""
        if not self.client and not self.connect():
            return

        # 1. Graph Statistics
        self.print_section("Graph Statistics")
        stats = self.client.get_stats()
        print(f"  Total Nodes:     {stats['nodes']}")
        print(f"  Total Edges:     {stats['edges']}")
        print("\n  Node Types:")
        for node_type, count in stats["node_types"].items():
            print(f"    - {node_type}: {count}")
        print("\n  Relationship Types:")
        for rel_type, count in stats["relationship_types"].items():
            print(f"    - {rel_type}: {count}")

        # 2. List All Nodes
        self.print_section("All Nodes in Graph")
        nodes = self.client._execute_query(
            """
        MATCH (n)
        RETURN n.id as id, labels(n)[0] as type, n.name as name, properties(n) as props
        ORDER BY type, name
        """
        )
        for node in nodes:
            print(f"\n  ID: {node['id']}")
            print(f"  Type: {node['type']}")
            print(f"  Name: {node['name']}")
            print(f"  Properties: {node['props']}")

        # 3. List All Relationships
        self.print_section("All Relationships in Graph")
        rels = self.client._execute_query(
            """
        MATCH (source)-[r]->(target)
        RETURN source.name as source_name, type(r) as relationship, target.name as target_name, properties(r) as props
        """
        )
        for rel in rels:
            print(
                f"\n  {rel['source_name']} --[{rel['relationship']}]--> {rel['target_name']}"
            )
            if rel["props"]:
                print(f"    Properties: {rel['props']}")

        # 4. Show Lineage Paths
        self.print_section("Lineage Paths")
        paths = self.client._execute_query(
            """
        MATCH path = (source)-[*1..3]->(target)
        WHERE source <> target
        RETURN [node in nodes(path) | node.name] as path_names, [rel in relationships(path) | type(rel)] as relationship_types
        LIMIT 10
        """
        )
        if paths:
            for idx, path in enumerate(paths, 1):
                path_str = " --> ".join(
                    f"{name} [{rel}]" if idx < len(path["relationship_types"]) else name
                    for idx, (name, rel) in enumerate(
                        zip(path["path_names"], path["relationship_types"] + [""])
                    )
                )
                print(f"\n  Path {idx}: {path_str}")
        else:
            print("\n  No lineage paths found (may need more data)")

        # 5. Cypher Query Examples
        self.print_section("Useful Cypher Queries")
        queries = [
            ("Find all tables", "MATCH (n:Table) RETURN n"),
            ("Find all columns", "MATCH (n:Column) RETURN n"),
            (
                "Get table with columns",
                "MATCH (t:Table)-[:CONTAINS]->(c:Column) RETURN t.name, collect(c.name)",
            ),
            (
                "Find upstream lineage",
                "MATCH (n {id: 'ENTITY_ID'})<-[*1..5]-(source) RETURN DISTINCT source",
            ),
            (
                "Search by name",
                "MATCH (n) WHERE toLower(n.name) CONTAINS 'customer' RETURN n",
            ),
        ]
        for idx, (desc, q) in enumerate(queries, 1):
            print(f"\n  {idx}. {desc}:")
            print(f"     {q}")

        # 6. Neo4j Browser Link
        self.print_section("Visualize in Neo4j Browser")
        print("\n  Open: https://console.neo4j.io")
        print("\n  Login with:")
        print(f"    URI:      {self.uri}")
        print(f"    Username: {self.username}")
        print(f"    Password: {self.password}")
        print("\n  Try this Cypher query:")
        print("    MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 25")

        self.close()
        print("\n" + "=" * 70)
        print("[+] Query session complete!")
        print("=" * 70 + "\n")


def verify_qdrant_connection():
    """Verify Qdrant connection and basic operations."""
    print("[*] Testing Qdrant connection...")

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    print(f"[*] Connecting to Qdrant at {qdrant_host}:{qdrant_port}...")

    try:
        client = QdrantClient(host=qdrant_host, port=qdrant_port)
        print("[+] Successfully connected to Qdrant!")

        collections = client.get_collections()
        print(f"\n[*] Existing collections: {len(collections.collections)}")
        for collection in collections.collections:
            print(f"    - {collection.name}")

        collection_name = "test_verification_embeddings"
        print(f"\n[*] Test: Creating test collection '{collection_name}'...")

        try:
            try:
                client.delete_collection(collection_name)
            except:
                pass

            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print(f"[+] Created collection '{collection_name}'")

            test_points = [
                PointStruct(id=1, vector=[0.1] * 768, payload={"text": "Smoke Test"})
            ]
            client.upsert(collection_name=collection_name, points=test_points)
            print("[+] Inserted test vector")

            client.delete_collection(collection_name)
            print("[+] Cleanup successful")
            print("\n[+] Qdrant verification passed!")
            return True

        except Exception as e:
            print(f"[!] Operation failed: {e}")
            return False

    except Exception as e:
        print(f"[!] Connection failed: {e}")
        return False


if __name__ == "__main__":
    inspector = GraphInspector()
    inspector.run_diagnostics()
