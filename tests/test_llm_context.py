import requests
import unittest
import time

BASE_URL = "http://localhost:8000/api/v1"


class TestLLMContextInjection(unittest.TestCase):
    def setUp(self):
        # Create a test project
        self.project_id = f"llm_test_proj_{int(time.time())}"
        payload = {
            "id": self.project_id,
            "name": "LLM Context Test Project",
            "description": "Testing context injection",
        }
        resp = requests.post(f"{BASE_URL}/projects", json=payload)
        self.assertEqual(resp.status_code, 201)

        # Add context
        context = {
            "description": "This is a high-stakes financial project.",
            "format": "text",
            "source_entities": ["sensitive_data"],
            "target_entities": ["audit_log"],
            "domain_hints": ["compliance"],
        }
        requests.put(f"{BASE_URL}/projects/{self.project_id}/context", json=context)

    def tearDown(self):
        requests.delete(f"{BASE_URL}/projects/{self.project_id}?delete_data=true")

    def test_ingest_with_context(self):
        # Ingest SQL WITH project_id
        payload = {
            "sql_content": "SELECT * FROM sensitive_data",
            "dialect": "tsql",
            "source_file": "test_query.sql",
            "project_id": self.project_id,
        }

        resp = requests.post(f"{BASE_URL}/ingest/sql", json=payload)

        resp = requests.post(f"{BASE_URL}/ingest/sql", json=payload)

        if resp.status_code != 200:
            print(f"Ingest failed: {resp.status_code} {resp.text}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Verify context_applied flag is True
        self.assertTrue(
            data.get("context_applied"),
            "Context should be applied when project_id is provided and context exists",
        )

    def test_ingest_without_context(self):
        # Ingest SQL WITHOUT project_id
        payload = {
            "sql_content": "SELECT * FROM public_data",
            "dialect": "tsql",
            "source_file": "test_query_no_context.sql",
            # No project_id
        }

        resp = requests.post(f"{BASE_URL}/ingest/sql", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Verify context_applied flag is False
        self.assertFalse(
            data.get("context_applied"),
            "Context should NOT be applied when project_id is missing",
        )


if __name__ == "__main__":
    unittest.main()
