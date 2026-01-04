
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from knowledge_graph.neo4j_client import create_neo4j_client_from_env
from dotenv import load_dotenv

load_dotenv()

def inspect_lineage():
    client = create_neo4j_client_from_env()
    try:
        # Get overall stats first
        print("--- Graph Statistics ---")
        stats = client.get_stats()
        print(f"Nodes: {stats['nodes']}")
        print(f"Edges: {stats['edges']}")
        print(f"Node Types: {stats['node_types']}")
        
        # Try to find what groups/projects exist (using a broader search)
        # We look for any nodes that might represent a project or root container
        query = """
        MATCH (n)
        WHERE n.entity_type IN ['Project', 'Database', 'Schema']
        RETURN n.name as name, n.id as id, labels(n) as labels
        LIMIT 10
        """
        results = client._execute_query(query)
        
        print("\n--- Potential Project/Root Nodes ---")
        for r in results:
            print(f"  {r['labels'][0]}: {r['name']} ({r['id']})")
            
        # Mermaid Diagram for a sample of the graph (up to 50 rels)
        print("\n--- Sample Graph Diagram (Mermaid) ---")
        path_query = """
        MATCH (a)-[r]->(b)
        RETURN a.name as source, type(r) as rel, b.name as target
        LIMIT 50
        """
        paths = client._execute_query(path_query)
        
        if paths:
            print("graph TD")
            for p in paths:
                s = p['source'].replace(' ' , '_').replace('.', '_').replace('-', '_')
                t = p['target'].replace(' ' , '_').replace('.', '_').replace('-', '_')
                print(f"    {s} -->|{p['rel']}| {t}")
        else:
            print("(No relationships found for diagram)")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    inspect_lineage()
