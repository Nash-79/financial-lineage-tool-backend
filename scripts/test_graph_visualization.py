"""
Test script to verify Visual Graph Rendering feature.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.config import config
from src.services.agent_service import LocalSupervisorAgent
from src.services.ollama_service import OllamaClient
from src.services.qdrant_service import QdrantLocalClient
from src.knowledge_graph.neo4j_client import Neo4jGraphClient


async def main():
    print("[*] Testing Visual Graph Rendering Feature...")

    # Initialize Clients
    ollama = OllamaClient(host=config.OLLAMA_HOST)
    qdrant = QdrantLocalClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    neo4j = Neo4jGraphClient(
        uri=config.NEO4J_URI,
        username=config.NEO4J_USERNAME,
        password=config.NEO4J_PASSWORD,
    )

    agent = LocalSupervisorAgent(
        ollama=ollama,
        qdrant=qdrant,
        graph=neo4j,
        llm_model=config.LLM_MODEL,
        embedding_model=config.EMBEDDING_MODEL,
    )

    # Test query
    test_query = "Show me the Default Project"
    print(f"\n[*] Test Query: {test_query}")

    try:
        result = await agent.query(test_query)

        print(f"\n[*] Answer: {result.get('answer', 'No answer')[:200]}...")
        print(f"\n[*] Graph Data Present: {bool(result.get('graph_data'))}")

        if result.get("graph_data"):
            graph = result["graph_data"]
            print(f"    - Nodes: {len(graph.get('nodes', []))}")
            print(f"    - Edges: {len(graph.get('edges', []))}")

            if graph.get("nodes"):
                print("\n[*] Sample Nodes:")
                for node in graph["nodes"][:3]:
                    print(
                        f"    - {node['id']}: {node['data']['label']} ({node['data']['type']})"
                    )

            if graph.get("edges"):
                print("\n[*] Sample Edges:")
                for edge in graph["edges"][:3]:
                    print(
                        f"    - {edge['source']} -> {edge['target']} ({edge.get('label', 'N/A')})"
                    )

            print("\n[+] SUCCESS: Graph data is correctly formatted for React Flow!")
        else:
            print(
                "\n[-] WARNING: No graph data returned. This might be expected if no entities were found."
            )

    except Exception as e:
        print(f"\n[!] ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await ollama.close()
        await qdrant.close()
        neo4j.close()


if __name__ == "__main__":
    asyncio.run(main())
