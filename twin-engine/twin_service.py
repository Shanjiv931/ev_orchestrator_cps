"""Digital twin engine.

Subscribes to every MQTT topic namespace the simulation layer publishes on,
caches the latest state of every EV/charger/swap-kiosk/feeder/solar-site in
Redis, exposes an internal read API over HTTP, and streams every update to
connected clients over WebSocket. Twin state must reflect the underlying
MQTT message within 1 second (verified in tests/test_live_latency.py against
a running stack).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Set

import paho.mqtt.client as mqtt
import redis.asyncio as aioredis
import redis as sync_redis
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from twin_store import ENTITY_TYPES, decode_state_message, redis_key, redis_scan_pattern

logging.basicConfig(level=logging.INFO, format="%(asctime)s twin-engine %(message)s")
log = logging.getLogger("twin-engine")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

redis_async = aioredis.from_url(REDIS_URL, decode_responses=True)
_redis_sync: sync_redis.Redis | None = None  # created in startup; used from the MQTT thread
_mqtt_client: mqtt.Client | None = None
_main_loop: asyncio.AbstractEventLoop | None = None
_connected_clients: Set[WebSocket] = set()


def handle_message(redis_client: sync_redis.Redis, topic: str, raw_payload: bytes) -> dict | None:
    """Apply one incoming MQTT message to Redis; returns the stored envelope, or None if ignored.

    Deliberately a single round-trip (SET only, no separate index write) -
    under real load (~100+ msgs/sec from the simulation layer) a second
    blocking Redis call per message was enough to build an unbounded
    backlog and delay delivery by minutes. Entity listing instead uses
    SCAN over the `twin:{entity_type}:*` key pattern (see list_state)."""
    decoded = decode_state_message(topic, raw_payload)
    if decoded is None:
        return None
    entity_type, entity_id, payload = decoded
    key = redis_key(entity_type, entity_id)
    redis_client.set(key, json.dumps(payload))
    return {"entity_type": entity_type, "entity_id": entity_id, "key": key, "data": payload}


async def broadcast(envelope: dict) -> None:
    if not _connected_clients:
        return
    message = json.dumps(envelope)
    dead = []
    for ws in list(_connected_clients):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connected_clients.discard(ws)


def _on_mqtt_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
    assert _redis_sync is not None
    envelope = handle_message(_redis_sync, msg.topic, msg.payload)
    if envelope is not None and _main_loop is not None:
        asyncio.run_coroutine_threadsafe(broadcast(envelope), _main_loop)


def _start_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = _on_mqtt_message
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)
    client.subscribe("ev/telemetry/#")
    client.subscribe("charger/status/#")
    client.subscribe("swap/status/#")
    client.subscribe("feeder/load/#")
    client.subscribe("station/solar/#")
    client.loop_start()
    log.info("subscribed to all twin topic namespaces")
    return client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_sync, _mqtt_client, _main_loop
    _main_loop = asyncio.get_event_loop()
    _redis_sync = sync_redis.Redis.from_url(REDIS_URL, decode_responses=True)
    _mqtt_client = await asyncio.get_event_loop().run_in_executor(None, _start_mqtt_client)
    yield
    if _mqtt_client is not None:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()


app = FastAPI(title="Digital Twin Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/state/{entity_type}")
async def list_state(entity_type: str) -> dict:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=404, detail=f"unknown entity type: {entity_type}")
    keys = [key async for key in redis_async.scan_iter(match=redis_scan_pattern(entity_type), count=500)]
    if not keys:
        return {}
    prefix_len = len(f"twin:{entity_type}:")
    values = await redis_async.mget(keys)
    return {
        key[prefix_len:]: json.loads(value)
        for key, value in zip(keys, values)
        if value is not None
    }


@app.get("/state/{entity_type}/{entity_id}")
async def get_state(entity_type: str, entity_id: str) -> dict:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=404, detail=f"unknown entity type: {entity_type}")
    raw = await redis_async.get(redis_key(entity_type, entity_id))
    if raw is None:
        raise HTTPException(status_code=404, detail="no twin state for this entity yet")
    return json.loads(raw)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _connected_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
