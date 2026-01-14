import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load explicitly from .env to be sure
load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print(f"Testing connection to: {uri}")
print(f"User: {username}")
print(f"Password starts with: {password[:4] if password else 'None'}")

if not all([uri, username, password]):
    print("Missing credentials!")
    exit(1)

try:
    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        print("SUCCESS: Connection verified!")
        
        # Try a simple query
        with driver.session() as session:
            result = session.run("RETURN 1 AS num")
            record = result.single()
            print(f"Query Result: {record['num']}")
            
except Exception as e:
    print(f"FAILURE: {e}")
