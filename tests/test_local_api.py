"""
Test script for the local Financial Lineage Tool API.
This demonstrates that the tool is running completely locally with Ollama.
"""

import requests
import json

API_BASE = "http://localhost:8000"


def test_health():
    """Test the health endpoint."""
    print("=" * 60)
    print("Testing Health Endpoint")
    print("=" * 60)
    response = requests.get(f"{API_BASE}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_graph_stats():
    """Test graph statistics."""
    print("=" * 60)
    print("Testing Graph Statistics")
    print("=" * 60)
    response = requests.get(f"{API_BASE}/api/v1/graph/stats")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_simple_query():
    """Test a simple lineage query."""
    print("=" * 60)
    print("Testing Simple Lineage Query (using Ollama)")
    print("=" * 60)

    # This will use your local Ollama model
    query = {"question": "What is data lineage?", "include_validation": False}

    print(f"Query: {query['question']}")
    print("Sending request to Ollama (this may take 10-30 seconds)...")

    try:
        response = requests.post(
            f"{API_BASE}/api/v1/lineage/query", json=query, timeout=60
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"\nAnswer from Ollama (llama3.1:8b):")
            print("-" * 60)
            print(result.get("answer", "No answer provided"))
            print("-" * 60)
            print(f"Confidence: {result.get('confidence', 'N/A')}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.Timeout:
        print("Request timed out - Ollama might be processing")
    except Exception as e:
        print(f"Error: {e}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Financial Lineage Tool - Local API Tests")
    print("Running with: Ollama + Qdrant + NetworkX (100% FREE)")
    print("=" * 60 + "\n")

    # Run tests
    test_health()
    test_graph_stats()

    print("\nNOTE: The query test will use your local Ollama model.")
    print("This demonstrates that NO cloud APIs are being called.")
    print("You can monitor Ollama activity with: ollama ps")
    print()

    user_input = input("Do you want to test a query with Ollama? (y/n): ")
    if user_input.lower() == "y":
        test_simple_query()

    print("\n" + "=" * 60)
    print("Tests Complete!")
    print("=" * 60)
    print("\nYour API is running locally at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nServices Status:")
    print("  - Ollama (LLM): http://localhost:11434")
    print("  - Qdrant (Vector DB): http://localhost:6333")
    print("  - Gremlin (Graph DB): http://localhost:8182")
    print("=" * 60 + "\n")
