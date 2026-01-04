import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from knowledge_graph.neo4j_client import Neo4jGraphClient

load_dotenv()

def assign_default_project():
    client = Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    try:
        print("Connecting to Neo4j...")
        
        # 1. Create Default Project Node if it doesn't exist
        print("Ensuring 'Default Project' exists...")
        create_project_query = """
        MERGE (p:Project {name: 'Default Project', id: 'default_project'})
        RETURN p
        """
        client._execute_query(create_project_query)
        print("Default Project ensured.")

        # 2. Find orphan nodes (Table, Database, Schema, etc.) and link them
        # We look for nodes that are NOT Projects and do NOT have a BELONGS_TO relationship to a Project
        print("Finding orphan nodes...")
        
        # This query finds nodes that are not Projects and don't belong to any project, 
        # then links them to the Default Project
        link_query = """
        MATCH (n)
        WHERE NOT 'Project' IN labels(n) 
          AND NOT (n)-[:BELONGS_TO]->(:Project)
        WITH n
        MATCH (p:Project {id: 'default_project'})
        MERGE (n)-[:BELONGS_TO]->(p)
        SET n.project_id = 'default_project'
        RETURN count(n) as linked_count
        """
        
        result = client._execute_query(link_query)
        linked_count = result[0]['linked_count'] if result else 0
        
        print(f"Linked {linked_count} orphan nodes to 'Default Project'.")
        
        # 3. Verify
        verify_query = """
        MATCH (p:Project {id: 'default_project'})<-[:BELONGS_TO]-(n)
        RETURN count(n) as count
        """
        result = client._execute_query(verify_query)
        final_count = result[0]['count'] if result else 0
        print(f"Total nodes in Default Project: {final_count}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    assign_default_project()
