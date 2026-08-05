"""Pure mapping/serialization logic for the digital twin store, kept free of
MQTT/Redis/FastAPI so it is unit-testable without any live service.

Every MQTT topic namespace the simulation layer publishes on maps onto one
Redis hash-of-entities keyed by entity type, so the read API and WebSocket
broadcast share a single, consistent addressing scheme.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Tuple

TOPIC_PREFIX_TO_ENTITY_TYPE = {
    "ev/telemetry": "ev",
    "charger/status": "charger",
    "swap/status": "swap",
    "feeder/load": "feeder",
    "station/solar": "solar",
    "charger/fault": "charger_fault",
}

ENTITY_TYPES = set(TOPIC_PREFIX_TO_ENTITY_TYPE.values())


def topic_to_entity(topic: str) -> Optional[Tuple[str, str]]:
    """Map an MQTT topic to (entity_type, entity_id), or None if unrecognized."""
    parts = topic.split("/")
    if len(parts) < 3:
        return None
    prefix = "/".join(parts[:2])
    entity_id = "/".join(parts[2:])
    entity_type = TOPIC_PREFIX_TO_ENTITY_TYPE.get(prefix)
    if entity_type is None or not entity_id:
        return None
    return entity_type, entity_id


def redis_key(entity_type: str, entity_id: str) -> str:
    return f"twin:{entity_type}:{entity_id}"


def redis_scan_pattern(entity_type: str) -> str:
    return f"twin:{entity_type}:*"


def decode_state_message(topic: str, raw_payload: bytes) -> Optional[Tuple[str, str, dict]]:
    """Decode one incoming MQTT message into (entity_type, entity_id, enriched_payload)."""
    mapping = topic_to_entity(topic)
    if mapping is None:
        return None
    entity_type, entity_id = mapping
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload = dict(payload)
    payload["_twin_updated_at"] = datetime.now(timezone.utc).isoformat()
    return entity_type, entity_id, payload
