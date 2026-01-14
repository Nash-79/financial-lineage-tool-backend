import asyncio
import os
import sys
from dotenv import load_dotenv

# Add repo root to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.services.agent_service import LocalSupervisorAgent
from src.services.ollama_service import OllamaClient
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.services.qdrant_service import QdrantLocalClient

load_dotenv()


async def debug_query():
    print("--- Initializing Services ---")
    ollama = OllamaClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    neo4j = Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
    )
    # Init Qdrant with host/port
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
    qdrant = QdrantLocalClient(host=qdrant_host, port=qdrant_port)

    # Init Agent with models
    llm_model = os.getenv("LLM_MODEL", "llama3.1:8b")
    embed_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    agent = LocalSupervisorAgent(
        ollama=ollama,
        qdrant=qdrant,
        graph=neo4j,
        llm_model=llm_model,
        embedding_model=embed_model,
    )

    query = "How many projects level lineages do we have? Give me some details of each and present as diagrams for clarity"

    print(f"\n--- Running Query: {query} ---")
    try:
        response = await agent.query(query)
        print("\n--- FINAL RESPONSE ---")
        print(f"Length: {len(response)}")
        print(f"Content: {response}")
        print("----------------------")
    except Exception as e:
        print(f"\n!!! EXCEPTION !!!\n{e}")


if __name__ == "__main__":
    asyncio.run(debug_query())
