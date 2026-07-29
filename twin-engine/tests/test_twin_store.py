import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

from twin_store import decode_state_message, redis_key, redis_scan_pattern, topic_to_entity


def test_topic_to_entity_maps_all_five_namespaces():
    assert topic_to_entity("ev/telemetry/city-42") == ("ev", "city-42")
    assert topic_to_entity("charger/status/station-01-charger-0") == ("charger", "station-01-charger-0")
    assert topic_to_entity("swap/status/swap-01") == ("swap", "swap-01")
    assert topic_to_entity("feeder/load/feeder-01") == ("feeder", "feeder-01")
    assert topic_to_entity("station/solar/station-01") == ("solar", "station-01")


def test_topic_to_entity_rejects_unknown_namespace():
    assert topic_to_entity("unknown/thing/id1") is None


def test_topic_to_entity_rejects_malformed_topic():
    assert topic_to_entity("ev/telemetry") is None
    assert topic_to_entity("ev") is None


def test_redis_key_is_namespaced_by_entity_type():
    assert redis_key("ev", "city-42") == "twin:ev:city-42"
    assert redis_scan_pattern("ev") == "twin:ev:*"


def test_decode_state_message_enriches_with_twin_timestamp():
    result = decode_state_message("ev/telemetry/city-1", json.dumps({"battery_pct": 88.0}).encode())
    assert result is not None
    entity_type, entity_id, payload = result
    assert entity_type == "ev"
    assert entity_id == "city-1"
    assert payload["battery_pct"] == 88.0
    assert "_twin_updated_at" in payload


def test_decode_state_message_rejects_invalid_json():
    assert decode_state_message("ev/telemetry/city-1", b"not json") is None


def test_decode_state_message_rejects_unknown_topic():
    assert decode_state_message("unknown/x/y", b"{}") is None
