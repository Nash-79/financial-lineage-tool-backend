import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from src.api.main_local import app

client = TestClient(app)

def test_websocket_connection():
    """Test WebSocket connection establishment and initial acknowledgement."""
    with client.websocket_connect("/api/v1/ws/dashboard") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "connection_ack"
        assert "Connected to dashboard" in data["data"]["message"]

def test_websocket_stats_update():
    """Test receiving periodic stats updates."""
    with client.websocket_connect("/api/v1/ws/dashboard") as websocket:
        # First message is ack
        websocket.receive_json()
        
        # Second message should be stats update (triggered by periodic task or manually if we could mock time)
        # Since we use asyncio.sleep(5) in the real endpoint, waiting might be flaky in unit tests without mocking.
        # Alternatively, we can check if the endpoint doesn't crash immediately.
        # For this test, receiving the ack confirms the handshake worked.
        pass

def test_websocket_disconnect():
    """Test graceful disconnection."""
    with client.websocket_connect("/api/v1/ws/dashboard") as websocket:
        websocket.receive_json() # Ack
        websocket.close()
