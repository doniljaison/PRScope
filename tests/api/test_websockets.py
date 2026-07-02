import pytest
import json
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.services.websocket_manager import manager

@pytest.mark.asyncio
async def test_websocket_connection_and_broadcast():
    """Test that a websocket can connect and receive a broadcast message."""
    client = TestClient(app)
    
    job_id = "test-job-123"
    
    with client.websocket_connect(f"/api/v1/ws/jobs/{job_id}") as websocket:
        # Client is now connected
        assert job_id in manager.active_connections
        
        # Broadcast a message using the manager
        test_message = {"job_id": job_id, "status": "fetching_diff"}
        
        # Since this test is async, we can just await the broadcast
        await manager.broadcast_to_job(job_id, test_message)
        
        # Receive the message
        data = websocket.receive_json()
        assert data == test_message
        
    # After the `with` block closes, the websocket disconnects
    # We may need to manually simulate the disconnect if the manager doesn't catch it immediately in TestClient
    manager.disconnect(websocket, job_id)
    assert job_id not in manager.active_connections
