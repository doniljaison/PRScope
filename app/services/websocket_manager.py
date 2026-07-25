"""WebSocket connection manager with Redis Pub/Sub for real-time job updates."""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast_to_job(self, job_id: str, message: dict):
        if job_id not in self.active_connections:
            return
        dead_sockets = set()
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_sockets.add(connection)
        for dead_socket in dead_sockets:
            self.disconnect(dead_socket, job_id)


manager = ConnectionManager()


async def listen_to_redis_pubsub(redis_client):
    """Background task: forwards Redis Pub/Sub 'job_updates' to WebSocket clients."""
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("job_updates")
        logger.info("Subscribed to Redis channel 'job_updates'")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
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
