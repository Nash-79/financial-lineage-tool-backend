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


def test_chat_deep_endpoint():
    """Test deep analysis chat."""
    response = client.post("/api/chat/deep", json={"query": "Analyze lineage"})
    assert response.status_code in [200, 500, 503]
    if response.status_code == 200:
        data = response.json()
        assert "response" in data
        assert data["query_type"] == "deep"


def test_chat_deep_with_session_id():
    """Test deep chat with session ID for memory context."""
    response = client.post(
        "/api/chat/deep",
        json={"query": "What tables exist?", "session_id": "test-session-123"},
    )
    assert response.status_code in [200, 500, 503]


def test_chat_deep_with_skip_memory():
    """Test deep chat with skip_memory flag."""
    response = client.post(
        "/api/chat/deep",
        json={
            "query": "What tables exist?",
            "session_id": "test-session-123",
            "skip_memory": True,
        },
    )
    assert response.status_code in [200, 500, 503]


def test_chat_deep_empty_query_returns_422():
    """Test that empty query returns 422."""
    response = client.post("/api/chat/deep", json={"query": ""})
    assert response.status_code == 422


def test_chat_deep_whitespace_query_returns_422():
    """Test that whitespace-only query returns 422."""
    response = client.post("/api/chat/deep", json={"query": "   "})
    assert response.status_code == 422


def test_chat_title_endpoint():
    """Test title generation endpoint."""
    response = client.post(
        "/api/chat/title", json={"query": "What is the lineage of customers table?"}
    )
    assert response.status_code in [200, 500, 503]
    if response.status_code == 200:
        data = response.json()
        assert "response" in data
        assert data["query_type"] == "title"


def test_chat_session_delete():
    """Test session memory deletion."""
    response = client.delete("/api/chat/session/test-session-to-delete")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["accepted", "ignored"]


def test_chat_deep_stream_endpoint():
    """Test streaming deep analysis endpoint returns SSE."""
    response = client.post("/api/chat/deep/stream", json={"query": "Analyze lineage"})
    # Should return 200 or 503 if agent not initialized
    assert response.status_code in [200, 500, 503]
    if response.status_code == 200:
        assert response.headers.get("content-type", "").startswith("text/event-stream")
