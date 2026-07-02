"""
websocket_manager.py — Manages WebSocket connections and Redis Pub/Sub for real-time job updates.
"""
import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps job_id -> set of connected WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Keep track of active redis subscription tasks
        self._pubsub_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept a new WebSocket connection and track it by job_id."""
        await websocket.accept()
        
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
            
        self.active_connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job_id: {job_id}")

    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection when it disconnects."""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                # If no more connections for this job, cleanup
                del self.active_connections[job_id]
                # We could also cancel the pubsub task here, but for simplicity
                # we'll let it finish on its own or when the server stops.

    async def broadcast_to_job(self, job_id: str, message: dict):
        """Send a JSON message to all WebSockets connected to a specific job."""
        if job_id in self.active_connections:
            dead_sockets = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Error sending to WebSocket for job {job_id}: {e}")
                    dead_sockets.add(connection)
            
            # Cleanup any sockets that failed
            for dead_socket in dead_sockets:
                self.disconnect(dead_socket, job_id)

manager = ConnectionManager()

# Background task to listen to Redis and forward to WebSockets
async def listen_to_redis_pubsub(redis_client):
    """
    Long-running background task that listens to Redis Pub/Sub channel 'job_updates'
    and pushes those messages to the ConnectionManager.
    """
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("job_updates")
        logger.info("Subscribed to Redis channel 'job_updates'")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    # Message data should be a JSON string like: {"job_id": "123", "status": "fetching_diff"}
                    data = json.loads(message["data"].decode("utf-8"))
                    job_id = data.get("job_id")
                    if job_id:
                        await manager.broadcast_to_job(job_id, data)
                except Exception as e:
                    logger.error(f"Error processing pubsub message: {e}")
                    
    except asyncio.CancelledError:
        logger.info("Redis pub/sub listener cancelled")
    except Exception as e:
        logger.error(f"Redis pub/sub listener failed: {e}")
