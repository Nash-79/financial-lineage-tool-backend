import requests
import unittest
import time

BASE_URL = "http://localhost:8000/api/v1"


class TestProjectContextAPI(unittest.TestCase):
    def setUp(self):
        # Create a test project
        self.project_id = f"test_proj_{int(time.time())}"
        payload = {
            "id": self.project_id,
            "name": "Integration Test Project",
            "description": "Created for API testing",
        }
        resp = requests.post(f"{BASE_URL}/projects", json=payload)
        self.assertEqual(resp.status_code, 201)

    def tearDown(self):
        # Clean up
        requests.delete(f"{BASE_URL}/projects/{self.project_id}?delete_data=true")

    def test_context_lifecycle(self):
        # 1. GET initial context (empty)
        resp = requests.get(f"{BASE_URL}/projects/{self.project_id}/context")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("description"), "")  # Default empty string

        # 2. PUT Update context
        new_context = {
            "description": "Updated Description",
            "format": "text",
            "source_entities": ["source1", "source2"],
            "target_entities": ["target1"],
            "domain_hints": ["hint1"],
        }
        resp = requests.put(
            f"{BASE_URL}/projects/{self.project_id}/context", json=new_context
        )
        self.assertEqual(resp.status_code, 200)

        # 3. GET verify update
        resp = requests.get(f"{BASE_URL}/projects/{self.project_id}/context")
        data = resp.json()
        self.assertEqual(data["description"], "Updated Description")
        self.assertEqual(data["source_entities"], ["source1", "source2"])

    def test_upload_context_file(self):
        # Create a test markdown file with frontmatter
        md_content = """---
format: markdown
source_entities:
  - uploaded_source
target_entities:
  - uploaded_target
domain_hints:
  - uploaded_hint
---
# Uploaded Description

This description comes from the markdown body.
"""
        files = {"file": ("context.md", md_content, "text/markdown")}

        # Upload file
        resp = requests.post(
            f"{BASE_URL}/projects/{self.project_id}/context/upload", files=files
        )

        if resp.status_code != 200:
            print(f"Upload failed: {resp.text}")

        self.assertEqual(resp.status_code, 200)
        result = resp.json()
        self.assertEqual(result["status"], "success")
        self.assertIn(self.project_id, result["file_path"])

        # Verify extraction
        extracted = result["context_extracted"]
        self.assertEqual(extracted["source_entities"], ["uploaded_source"])
        self.assertIn("# Uploaded Description", extracted["description"])

        # Verify persistence via GET
        resp = requests.get(f"{BASE_URL}/projects/{self.project_id}/context")
        data = resp.json()
        self.assertEqual(data["domain_hints"], ["uploaded_hint"])


if __name__ == "__main__":
    unittest.main()
