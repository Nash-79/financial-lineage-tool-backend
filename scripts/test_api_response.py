"""
Quick test to verify the API response structure.
Run this and paste the output to diagnose the issue.
"""

import requests
import json

url = "http://localhost:8000/api/chat/deep"
payload = {
    "query": "Show me the Default Project",
    "session_id": "test-session-123"
}

print("[*] Sending request to:", url)
print("[*] Payload:", json.dumps(payload, indent=2))

try:
    response = requests.post(url, json=payload, timeout=60)
    print(f"\n[*] Status Code: {response.status_code}")
    print(f"[*] Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[*] Response Keys: {list(data.keys())}")
        print(f"[*] Response Text (first 200 chars): {data.get('response', '')[:200]}")
        print(f"[*] Has graph_data: {bool(data.get('graph_data'))}")
        
        if data.get('graph_data'):
            print(f"\n[+] Graph Data Found!")
            print(f"    - Nodes: {len(data['graph_data'].get('nodes', []))}")
            print(f"    - Edges: {len(data['graph_data'].get('edges', []))}")
        else:
            print(f"\n[-] No graph_data in response")
            print(f"[*] Full Response:\n{json.dumps(data, indent=2)}")
    else:
        print(f"\n[!] Error Response: {response.text}")
        
except Exception as e:
    print(f"\n[!] Request failed: {e}")
    import traceback
    traceback.print_exc()
