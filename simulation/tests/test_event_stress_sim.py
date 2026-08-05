import random
import sys
from pathlib import Path

import simpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from event_stress_sim import run_burst
from station_sim import STATION_PROFILES


def test_burst_restores_baseline_profile_after_completion():
    spec_type = "public_dc_hub"
    baseline_before = STATION_PROFILES[spec_type]
    events = []

    run_burst("station-vit-dc-01", density_multiplier=5.0, burst_minutes=5,
              publish=events.append, env=simpy.Environment())

    assert STATION_PROFILES[spec_type] == baseline_before


def test_burst_restores_baseline_profile_even_if_publish_raises():
    spec_type = "public_dc_hub"
    baseline_before = STATION_PROFILES[spec_type]

    def failing_publish(payload):
        raise RuntimeError("simulated MQTT failure")

    try:
        run_burst("station-vit-dc-01", density_multiplier=5.0, burst_minutes=5,
                  publish=failing_publish, env=simpy.Environment())
    except RuntimeError:
        pass

    assert STATION_PROFILES[spec_type] == baseline_before


def test_higher_density_multiplier_produces_more_sessions_in_the_same_window():
    random.seed(11)
    events_low = []
    run_burst("station-vit-dc-01", density_multiplier=1.0, burst_minutes=180,
              publish=events_low.append, env=simpy.Environment())

    random.seed(11)
    events_high = []
    run_burst("station-vit-dc-01", density_multiplier=8.0, burst_minutes=180,
              publish=events_high.append, env=simpy.Environment())

    occupied_low = sum(1 for e in events_low if e["status"] == "occupied")
    occupied_high = sum(1 for e in events_high if e["status"] == "occupied")
    assert occupied_high > occupied_low


def test_unknown_station_id_raises():
    import pytest

    with pytest.raises(ValueError):
        run_burst("not-a-real-station", density_multiplier=2.0, burst_minutes=1,
                  publish=lambda p: None, env=simpy.Environment())
