import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin_service import handle_message


class FakeRedis:
    """Minimal in-memory stand-in for the one redis-py call handle_message
    makes, so this test needs no live Redis server."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self.store[key] = value


def test_handle_message_stores_value():
    fake = FakeRedis()
    payload = json.dumps({"battery_pct": 77.0}).encode()
    envelope = handle_message(fake, "ev/telemetry/city-9", payload)

    assert envelope["entity_type"] == "ev"
    assert envelope["entity_id"] == "city-9"
    assert fake.store["twin:ev:city-9"] is not None
    stored = json.loads(fake.store["twin:ev:city-9"])
    assert stored["battery_pct"] == 77.0
    assert "_twin_updated_at" in stored


def test_handle_message_ignores_unknown_topic():
    fake = FakeRedis()
    result = handle_message(fake, "not/a/known/topic", b"{}")
    assert result is None
    assert fake.store == {}


def test_handle_message_overwrites_previous_state_for_same_entity():
    fake = FakeRedis()
    handle_message(fake, "charger/status/c1", json.dumps({"status": "occupied"}).encode())
    handle_message(fake, "charger/status/c1", json.dumps({"status": "available"}).encode())

    stored = json.loads(fake.store["twin:charger:c1"])
    assert stored["status"] == "available"
