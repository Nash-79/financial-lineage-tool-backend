"""
Corpus ingestion logic to walk directories and process files.
"""

import os
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.ingestion.code_parser import CodeParser
from src.knowledge_graph.entity_extractor import GraphExtractor


def ingest_corpus_from_dir(target_dir: str):
    """
    Recursively ingest files from target directory.
    """
    print(f"[*] Starting ingestion for directory: {target_dir}")

    # 1. Connect to Neo4j
    try:
        client = Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )
        print("[+] Connected to Neo4j")
    except Exception as e:
        print(f"[!] Failed to connect to Neo4j: {e}")
        return

    try:
        # 2. Setup Components
        parser = CodeParser()
        extractor = GraphExtractor(client, parser)

        # 3. Walk and Ingest
        supported_exts = (".sql", ".py", ".json")
        files_processed = 0

        for root, dirs, files in os.walk(target_dir):
            # Ignore hidden directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d != "__pycache__" and d != "venv"
            ]

            for file in files:
                if file.lower().endswith(supported_exts):
                    file_path = os.path.join(root, file)
                    extractor.ingest_file(file_path)
                    files_processed += 1

        print("\n" + "=" * 60)
        print("  Ingestion Complete!")
        print(f"  Files Processed: {files_processed}")
        print("=" * 60)

    finally:
        client.close()
