"""
Test Qdrant connection and embedding storage.
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Load environment variables
load_dotenv()


def test_qdrant():
    """Test Qdrant connection and operations."""

    print("[*] Testing Qdrant connection...")

    # Get configuration from environment
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

    print(f"[*] Connecting to Qdrant at {qdrant_host}:{qdrant_port}...")

    try:
        # Create client
        client = QdrantClient(host=qdrant_host, port=qdrant_port)

        print("[+] Successfully connected to Qdrant!")

        # List existing collections
        collections = client.get_collections()
        print(f"\n[*] Existing collections: {len(collections.collections)}")
        for collection in collections.collections:
            print(f"    - {collection.name}")

        # Test 1: Create a test collection
        collection_name = "test_embeddings"
        print(f"\n[*] Test 1: Creating test collection '{collection_name}'...")

        try:
            # Delete if exists
            try:
                client.delete_collection(collection_name)
                print(f"[i] Deleted existing collection")
            except:
                pass

            # Create new collection
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print(f"[+] Created collection '{collection_name}'")

        except Exception as e:
            print(f"[!] Error creating collection: {e}")
            return False

        # Test 2: Insert test vectors
        print(f"\n[*] Test 2: Inserting test vectors...")

        try:
            # Create dummy vectors (768-dimensional for nomic-embed-text)
            test_points = [
                PointStruct(
                    id=1,
                    vector=[0.1] * 768,
                    payload={"text": "Customer table", "type": "Table"},
                ),
                PointStruct(
                    id=2,
                    vector=[0.2] * 768,
                    payload={"text": "Product table", "type": "Table"},
                ),
                PointStruct(
                    id=3,
                    vector=[0.3] * 768,
                    payload={"text": "CustomerID column", "type": "Column"},
                ),
            ]

            client.upsert(collection_name=collection_name, points=test_points)
            print(f"[+] Inserted 3 test vectors")

        except Exception as e:
            print(f"[!] Error inserting vectors: {e}")
            return False

        # Test 3: Search
        print(f"\n[*] Test 3: Searching for similar vectors...")

        try:
            # Search using a query vector
            search_result = client.query_points(
                collection_name=collection_name, query=[0.15] * 768, limit=2
            )

            print(f"[+] Found {len(search_result.points)} results:")
            for hit in search_result.points:
                print(f"    - {hit.payload['text']} (score: {hit.score:.4f})")

        except Exception as e:
            print(f"[!] Error searching: {e}")
            return False

        # Test 4: Get collection info
        print(f"\n[*] Test 4: Getting collection info...")

        try:
            collection_info = client.get_collection(collection_name)
            print(f"[+] Collection info:")
            print(f"    - Points count: {collection_info.points_count}")
            print(f"    - Vector size: {collection_info.config.params.vectors.size}")
            print(f"    - Distance: {collection_info.config.params.vectors.distance}")

        except Exception as e:
            print(f"[!] Error getting collection info: {e}")
            return False

        # Cleanup
        print(f"\n[*] Cleaning up test collection...")
        client.delete_collection(collection_name)
        print(f"[+] Test collection deleted")

        print("\n[+] All Qdrant tests passed!")
        return True

    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_qdrant()
    exit(0 if success else 1)
