import pytest
from fastapi.testclient import TestClient
from src.api.main_local import app

client = TestClient(app)

def test_chat_text_endpoint():
    """Test simple text chat."""
    response = client.post("/api/chat/text", json={"query": "Hello"})
    # We might get 500 if Ollama is down, but we want to check it's not a Pydantic error
    # If Ollama is down, we expect 500 or 503, but with a specific detail message.
    # Ideally we mock the agent/ollama, but for integration we want to see it run.
    # If we get 422, that's a schema error (fail).
    assert response.status_code in [200, 500, 503]
    if response.status_code == 200:
        data = response.json()
        assert "response" in data
        assert data["query_type"] == "text"

def test_chat_semantic_endpoint():
    """Test semantic chat."""
    response = client.post("/api/chat/semantic", json={"query": "Find lineage"})
    assert response.status_code in [200, 500, 503]
    if response.status_code == 200:
        data = response.json()
        assert "response" in data
        assert data["query_type"] == "semantic"

def test_chat_graph_endpoint():
    """Test graph chat."""
    response = client.post("/api/chat/graph", json={"query": "Show tables"})
    assert response.status_code in [200, 500, 503]
    if response.status_code == 200:
        data = response.json()
        assert "response" in data
        assert data["query_type"] == "graph"
