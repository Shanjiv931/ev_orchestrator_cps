"""Relays twin-engine's live WebSocket feed to the backend's own connected
clients. Frontend clients talk only to the backend (REST + WebSocket);
twin-engine stays an internal-only service per Section 4.3.
"""
import asyncio
import logging
from typing import Set

import websockets
from fastapi import WebSocket

log = logging.getLogger("twin-client")

_connected_clients: Set[WebSocket] = set()


def register(websocket: WebSocket) -> None:
    _connected_clients.add(websocket)


def unregister(websocket: WebSocket) -> None:
    _connected_clients.discard(websocket)


async def _broadcast(message: str) -> None:
    if not _connected_clients:
        return
    dead = []
    for ws in list(_connected_clients):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connected_clients.discard(ws)


async def relay_forever(twin_ws_url: str) -> None:
    """Reconnects indefinitely; safe to run as a background task for the
    lifetime of the app."""
    while True:
        try:
            async with websockets.connect(twin_ws_url) as twin_ws:
                log.info("connected to twin-engine at %s", twin_ws_url)
                async for message in twin_ws:
                    await _broadcast(message)
        except (ConnectionRefusedError, OSError, websockets.exceptions.WebSocketException) as exc:
            log.warning("twin-engine connection lost (%s), retrying in 2s", exc)
            await asyncio.sleep(2)
