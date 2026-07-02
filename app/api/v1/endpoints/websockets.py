from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time streaming of job status updates.
    """
    await manager.connect(websocket, job_id)
    try:
        # We just keep the connection open to send data from the server side.
        # If the client sends data, we can ignore it or process it, but for status
        # streaming, we typically just loop and wait.
        while True:
            # Wait for any messages from client just to keep connection alive
            # and detect disconnects natively.
            data = await websocket.receive_text()
            logger.debug(f"Received from WS client {job_id}: {data}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from job: {job_id}")
        manager.disconnect(websocket, job_id)
