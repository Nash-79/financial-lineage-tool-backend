"""Create InvestmentData project and ingest demo files."""

import requests

API_BASE = "http://localhost:8000"

# Step 1: Create project
print("Creating InvestmentData project...")
response = requests.post(
    f"{API_BASE}/api/v1/projects",
    json={
        "name": "InvestmentData",
        "description": "Multi-hop SQL lineage demo: Postgres → Python → SQL Server",
        "status": "active",
    },
)

if response.status_code == 200:
    project = response.json()
    project_id = project["id"]
    print(f"✅ Project created: {project_id}")
    print(f"   Name: {project['name']}")

    # Write project ID to file for ingestion script
    with open("scripts/.project_id", "w") as f:
        f.write(project_id)

    print(f"\n✅ Project ID saved to scripts/.project_id")
    print(f"\nNow run: python scripts/ingest_demo_data.py")
else:
    print(f"❌ Failed to create project ({response.status_code})")
    print(response.text)
