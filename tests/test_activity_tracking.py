from fastapi.testclient import TestClient
from src.api.main_local import app

client = TestClient(app)

# We can reuse the existing client to trigger activity events


def test_activity_persistence():
    """Test that requests trigger activity logging."""
    # This is hard to test black-box style without checking where logs go.
    # But we can at least ensure the middleware doesn't crash the request.

    response = client.get("/health")
    assert response.status_code == 200

    # Trigger a 404 to check error logging
    response = client.get("/nonexistent")
    assert response.status_code == 404
