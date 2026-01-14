"""Ingest demo files into the lineage tool for benchmarking."""

import requests
from pathlib import Path

API_BASE = "http://localhost:8000"
DEMO_DIR = Path(__file__).parent.parent / "demo_data"

# Use existing InvestmentData project ID
PROJECT_ID = "8ae9366d-a5da-44a3-a0d0-c0d2355b9b97"

files_to_ingest = [
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


def ingest_files():
    """Upload all demo files to the lineage tool."""
    for file_info in files_to_ingest:
        file_path = file_info["path"]
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            continue

        print(f"\n📤 Uploading: {file_path.name}")

        with open(file_path, "rb") as f:
            files = {"files": (file_path.name, f, "text/plain")}
            data = {
                "project_id": PROJECT_ID,
                "repository_name": file_info["repository_name"],
                "dialect": file_info.get("dialect", "auto"),
            }

            response = requests.post(
                f"{API_BASE}/api/v1/files/upload", files=files, data=data
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"   Repository: {file_info['repository_name']}")
                if "results" in result and len(result["results"]) > 0:
                    file_result = result["results"][0]
                    print(f"   Nodes created: {file_result.get('nodes_created', 0)}")
                    print(f"   Status: {file_result.get('status', 'unknown')}")
            else:
                print(f"❌ Failed ({response.status_code}): {response.text[:200]}")


if __name__ == "__main__":
    print("=" * 60)
    print("Ingesting Demo Data for LLM Benchmarking")
    print(f"Project: InvestmentData ({PROJECT_ID})")
    print("=" * 60)
    ingest_files()
    print("\n✅ Ingestion complete!")
