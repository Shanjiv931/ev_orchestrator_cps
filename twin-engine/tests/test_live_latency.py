"""Section 4.3's explicit acceptance test: twin state must reflect the
underlying MQTT message within 1 second, verified directly against a running
stack (not mocked). Section 9.3 also requires a direct comparison between
twin state and simulation output.

Skipped automatically when the docker compose stack isn't up (e.g. in CI,
which doesn't run the full stack) rather than failing.
"""
import json
import time
import uuid

import httpx
import paho.mqtt.publish as publish
import pytest

MQTT_HOST = "localhost"
MQTT_PORT = 1883
API_BASE = "http://localhost:8100"


def _stack_is_up() -> bool:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _stack_is_up(), reason="live docker compose stack not running")


def test_twin_state_reflects_new_mqtt_message_within_one_second():
    vehicle_id = f"latency-test-{uuid.uuid4().hex[:8]}"
    payload = {"vehicle_id": vehicle_id, "battery_pct": 42.0, "lat": 12.9, "lon": 77.6}

    start = time.monotonic()
    publish.single(f"ev/telemetry/{vehicle_id}", json.dumps(payload), hostname=MQTT_HOST, port=MQTT_PORT)

    deadline = start + 1.0
    seen = None
    with httpx.Client() as client:
        while time.monotonic() < deadline:
            r = client.get(f"{API_BASE}/state/ev/{vehicle_id}")
            if r.status_code == 200:
                seen = r.json()
                break
            time.sleep(0.02)

    elapsed = time.monotonic() - start
    assert seen is not None, "twin state was not visible via the read API within 1 second"
    assert seen["battery_pct"] == 42.0
    assert elapsed <= 1.0


def test_twin_state_matches_published_payload_directly():
    feeder_id = f"latency-test-feeder-{uuid.uuid4().hex[:8]}"
    payload = {"feeder_id": feeder_id, "current_load_kw": 123.4, "capacity_kw": 500.0}
    publish.single(f"feeder/load/{feeder_id}", json.dumps(payload), hostname=MQTT_HOST, port=MQTT_PORT)

    time.sleep(0.5)
    r = httpx.get(f"{API_BASE}/state/feeder/{feeder_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["current_load_kw"] == 123.4
    assert body["capacity_kw"] == 500.0
