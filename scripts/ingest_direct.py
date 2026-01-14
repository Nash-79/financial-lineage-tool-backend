"""Ingest demo files directly using local IngestionPipeline.

Bypasses the running backend server to ensure the latest chunking logic is used.
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file
from dotenv import load_dotenv

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.services.ingestion_pipeline import index_file_content
from src.ingestion.code_parser import CodeParser
from src.knowledge_graph.entity_extractor import GraphExtractor
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.services.ollama_service import OllamaClient
from src.services.qdrant_service import QdrantLocalClient
from src.api.config import config
from fastapi import UploadFile

# Demo files config
DEMO_DIR = Path(__file__).parent.parent / "demo_data"
PROJECT_ID = "8ae9366d-a5da-44a3-a0d0-c0d2355b9b97"

FILES_TO_INGEST = [
    {
        "path": DEMO_DIR / "postgres_investments.sql",
        "repository_name": "Postgres Landing & Staging",
        "dialect": "postgres",
    },
    {
        "path": DEMO_DIR / "etl_postgre_to_sql.py",
        "repository_name": "Python ETL Pipeline",
        "dialect": "auto",
    },
    {
        "path": DEMO_DIR / "sql_Investments_objects.sql",
        "repository_name": "SQL Server Warehouse",
        "dialect": "tsql",
    },
]


class MockState:
    """Mock application state."""

    def __init__(self, ollama, qdrant, graph):
        self.ollama = ollama
        self.qdrant = qdrant
        self.graph = graph
        self.llamaindex_service = None  # Disable LlamaIndex for this script


async def direct_ingestion():
    print("=" * 60)
    print("Starting Direct Ingestion (Bypassing Server)")
    print(f"Project: {PROJECT_ID}")
    print("=" * 60)

    # Initialize services
    print("[*] Initializing services...")

    # Redis (optional but good for caching)
    redis_client = None
    try:
        import redis.asyncio as redis

        redis_client = redis.Redis(
            host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True
        )
        await redis_client.ping()
        print("[+] Redis connected")
    except Exception:
        print("[!] Redis not available, skipping cache")

    # Clients
    ollama = OllamaClient(host=config.OLLAMA_HOST, redis_client=redis_client)
    qdrant = QdrantLocalClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

    graph = Neo4jGraphClient(
        uri=config.NEO4J_URI,
        username=config.NEO4J_USERNAME,
        password=config.NEO4J_PASSWORD,
        database=config.NEO4J_DATABASE,
    )

    state = MockState(ollama, qdrant, graph)

    # Ensure Qdrant collection
    await qdrant.create_collection("code_chunks", vector_size=768)

    print("[+] Services ready. Processing files...")

    for file_info in FILES_TO_INGEST:
        file_path = file_info["path"]
        repo_name = file_info["repository_name"]
        dialect = file_info["dialect"]

        print(f"\nProcessing: {file_path.name}")
        print(f"  Repository: {repo_name}")
        print(f"  Dialect: {dialect}")

        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Run ingestion
        try:
            result = await index_file_content(
                content=content,
                file_path=str(file_path),
                state=state,
                ingestion_id=f"direct_{file_path.name}",
                project_id=PROJECT_ID,
                repository_id=repo_name,
                dialect=dialect,
                tracker=None,
            )

            # Print summary
            chunks = result.get("chunks", 0)
            indexed = result.get("indexed", 0)
            print(f"✅ Vector Ingestion: Created {chunks} chunks, Indexed {indexed}")

            # --- Graph Ingestion Track ---
            print(f"[*] Starting Graph Extraction for {file_path.name}...")
            extractor = GraphExtractor(state.graph, CodeParser())

            nodes_created = 0
            if file_path.suffix.lower() == ".sql":
                nodes_created = extractor.ingest_sql_lineage(
                    sql_content=content,
                    dialect=dialect,
                    source_file=file_path.name,
                    project_id=PROJECT_ID,
                    repository_id=repo_name,
                )
            elif file_path.suffix.lower() == ".py":
                # For Python, using ingest_file wrapper which includes parsing logic details
                # But to call specifics or use similar pattern:
                extractor.ingest_file(str(file_path))
                nodes_created = "N/A (Python)"

            extractor.flush_batch()
            print(f"✅ Graph Ingestion: Created {nodes_created} nodes/edges")

        except Exception as e:
            print(f"❌ Failed: {e}")
            import traceback

            traceback.print_exc()

    # Cleanup
    await ollama.close()
    await qdrant.close()
    if hasattr(graph, "close"):
        graph.close()
    if redis_client:
        await redis_client.aclose()

    print("\n✅ Direct Ingestion Complete!")


if __name__ == "__main__":
    asyncio.run(direct_ingestion())
