
import os
from dotenv import load_dotenv
from src.knowledge_graph.neo4j_client import Neo4jGraphClient

def verify():
    load_dotenv()
    
    neo4j_client = Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    
    query = "MATCH (n:SchemaMetadata) RETURN n"
    try:
        results = neo4j_client._execute_query(query, {})
        print(f"Found {len(results)} SchemaMetadata nodes.")
        for record in results:
            print(record)
    except Exception as e:
        print(f"Error querying Neo4j: {e}")
    finally:
        neo4j_client.close()

if __name__ == "__main__":
    verify()
