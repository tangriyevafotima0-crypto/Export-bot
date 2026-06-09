"""Real-time WebSocket routes for the dashboard.

Manages WebSocket connections and broadcasts live events
(story views, online status changes, bio link clicks, alerts)
to all connected dashboard clients.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

_connected_clients: list[WebSocket] = []
_broadcast_lock = asyncio.Lock()


async def broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients.

    Args:
        event_type: Type of event (story_view, online_change, bio_click, alert).
        data: Event payload data.
    """
    message = json.dumps({"type": event_type, "data": data, "timestamp": _get_timestamp()})
    disconnected = []

    async with _broadcast_lock:
        for client in _connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)

        for client in disconnected:
            if client in _connected_clients:
                _connected_clients.remove(client)

    if disconnected:
        logger.debug(f"Removed {len(disconnected)} disconnected clients")


def _get_timestamp() -> str:
    """Get current UTC timestamp as ISO format string."""
    from datetime import datetime
    return datetime.utcnow().isoformat()


@router.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time dashboard updates.

    Accepts connections and keeps them alive until disconnect.
    Connected clients receive broadcasts of all monitoring events.
    """
    await websocket.accept()
    _connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(_connected_clients)}")

    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"message": "Connected to real-time feed"},
            "timestamp": _get_timestamp(),
        }))

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "data": {},
                        "timestamp": _get_timestamp(),
                    }))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "type": "heartbeat",
                    "data": {},
                    "timestamp": _get_timestamp(),
                }))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        if websocket in _connected_clients:
            _connected_clients.remove(websocket)
        logger.debug(f"WebSocket clients remaining: {len(_connected_clients)}")


def get_connected_count() -> int:
    """Get the number of currently connected WebSocket clients.

    Returns:
        int: Number of active connections.
    """
    return len(_connected_clients)
