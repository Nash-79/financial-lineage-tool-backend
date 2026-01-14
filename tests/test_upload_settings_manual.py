"""Test upload settings persistence by adding .md extension."""

import requests
import json

# Test 1: Get current settings
print("=" * 80)
print("TEST 1: Get current upload settings")
print("=" * 80)

response = requests.get("http://localhost:8000/api/v1/files/config")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 2: Add .md extension
print("\n" + "=" * 80)
print("TEST 2: Add .md file extension")
print("=" * 80)

new_settings = {
    "allowed_extensions": [".sql", ".py", ".json", ".csv", ".md", ".ddl", ".ipynb"]
}

response = requests.put("http://localhost:8000/api/v1/files/config", json=new_settings)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"Response: {json.dumps(response.json(), indent=2)}")
else:
    print(f"Error: {response.text}")

# Test 3: Verify settings persisted
print("\n" + "=" * 80)
print("TEST 3: Verify settings persisted")
print("=" * 80)

response = requests.get("http://localhost:8000/api/v1/files/config")
print(f"Status: {response.status_code}")
settings = response.json()
print(f"Response: {json.dumps(settings, indent=2)}")

# Check if .md is in the list
if ".md" in settings.get("allowed_extensions", []):
    print("\n✅ SUCCESS: .md extension added and persisted!")
    print(f"   Persisted: {settings.get('persisted', False)}")
    print(f"   Source: {settings.get('source', 'unknown')}")
    print(f"   Last Updated: {settings.get('last_updated', 'N/A')}")
else:
    print("\n❌ FAILED: .md extension not found in settings")
