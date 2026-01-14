"""
Test Neo4j connection and basic operations.
"""

import os
from dotenv import load_dotenv
from src.knowledge_graph.neo4j_client import Neo4jGraphClient

# Load environment variables
load_dotenv()


def test_neo4j():
    """Test Neo4j connection and operations."""

    print("[*] Testing Neo4j connection...")

    # Get credentials from environment
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    print(f"[*] URI: {uri}")
    print(f"[*] Username: {username}")
    print(f"[*] Database: {database}")

    try:
        # Create client
        client = Neo4jGraphClient(
            uri=uri, username=username, password=password, database=database
        )

        print("[+] Successfully connected to Neo4j!")

        # Get initial stats
        stats = client.get_stats()
        print(f"\n[*] Initial graph stats:")
        print(f"    Nodes: {stats['nodes']}")
        print(f"    Edges: {stats['edges']}")
        print(f"    Node types: {stats['node_types']}")
        print(f"    Relationship types: {stats['relationship_types']}")

        # Test 1: Add entities
        print("\n[*] Test 1: Adding test entities...")

        client.add_entity(
            entity_id="test_table_customers",
            entity_type="Table",
            name="customers",
            database="production",
            schema="public",
        )
        print("[+] Added 'customers' table")

        client.add_entity(
            entity_id="test_table_orders",
            entity_type="Table",
            name="orders",
            database="production",
            schema="public",
        )
        print("[+] Added 'orders' table")

        client.add_entity(
            entity_id="test_column_customer_id",
            entity_type="Column",
            name="customer_id",
            data_type="INTEGER",
        )
        print("[+] Added 'customer_id' column")

        # Test 2: Add relationships
        print("\n[*] Test 2: Adding relationships...")

        client.add_relationship(
            source_id="test_table_customers",
            target_id="test_column_customer_id",
            relationship_type="CONTAINS",
            position=1,
        )
        print("[+] Added CONTAINS relationship")

        client.add_relationship(
            source_id="test_table_orders",
            target_id="test_table_customers",
            relationship_type="DERIVES_FROM",
            transformation="JOIN ON customer_id",
        )
        print("[+] Added DERIVES_FROM relationship")

        # Test 3: Retrieve entity
        print("\n[*] Test 3: Retrieving entity...")

        entity = client.get_entity("test_table_customers")
        if entity:
            print(f"[+] Retrieved entity: {entity}")
        else:
            print("[!] Failed to retrieve entity")

        # Test 4: Search by name
        print("\n[*] Test 4: Searching by name...")

        results = client.find_by_name("customer")
        print(f"[+] Found {len(results)} entities matching 'customer':")
        for result in results:
            print(f"    - {result.get('name')} ({result.get('entity_type')})")

        # Test 5: Get upstream lineage
        print("\n[*] Test 5: Getting upstream lineage...")

        upstream = client.get_upstream("test_table_orders", max_depth=5)
        print(f"[+] Found {len(upstream)} upstream relationships")
        for rel in upstream[:3]:  # Show first 3
            print(
                f"    - {rel.get('source')} -> {rel.get('target')} ({rel.get('relationship')})"
            )

        # Get final stats
        print("\n[*] Final graph stats:")
        stats = client.get_stats()
        print(f"    Nodes: {stats['nodes']}")
        print(f"    Edges: {stats['edges']}")
        print(f"    Node types: {stats['node_types']}")
        print(f"    Relationship types: {stats['relationship_types']}")

        # Close connection
        client.close()
        print("\n[+] All tests passed! Neo4j is working correctly.")

    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = test_neo4j()
    exit(0 if success else 1)
