import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import simpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from registry import StationSpec
from station_sim import STATION_PROFILES, Station


class _FakeClock:
    """Ticks forward by one second per call so timestamp equality checks are
    deterministic instead of depending on OS clock resolution - the whole
    simulated scenario below runs in a handful of real milliseconds, which
    can otherwise make two consecutive datetime.now() calls collide."""

    _counter = 0

    @classmethod
    def now(cls, tz=None):
        cls._counter += 1
        return datetime.fromtimestamp(1750000000 + cls._counter, tz=timezone.utc)


def test_housing_society_sessions_are_far_longer_than_dc_hub_sessions():
    """The housing-society booking/queue problem is structurally different
    from the DC-hub wait-time problem: overnight sessions, not fast charges."""
    _, dc_hub_session, _, _ = STATION_PROFILES["public_dc_hub"]
    _, housing_session, _, _ = STATION_PROFILES["housing_society_ac"]
    assert housing_session > 10 * dc_hub_session


def test_occupied_events_are_always_freshly_verified():
    spec = StationSpec("s-dc", "public_dc_hub", "feeder-x", num_chargers=2, charger_power_kw=60.0)
    env = simpy.Environment()
    events = []
    random.seed(7)
    station = Station(env=env, spec=spec, publish=events.append)
    env.process(station.arrivals())
    env.run(until=300)

    occupied_events = [e for e in events if e["status"] == "occupied"]
    assert len(occupied_events) >= 3
    for e in occupied_events:
        assert e["last_verified_at"] == e["reported_at"]
        assert e["power_kw"] == spec.charger_power_kw


def test_flaky_charger_can_report_available_with_stale_verification():
    """Reported-vs-verified trust layer: a flaky charger can flip status to
    'available' without a fresh last_verified_at - the recommendation
    ranking (Phase 5) must be able to see and penalize this gap."""
    spec = StationSpec("s-flaky", "public_dc_hub", "feeder-x", num_chargers=1, charger_power_kw=60.0)
    env = simpy.Environment()
    events = []

    with patch("station_sim.random.random", return_value=0.1), \
         patch("station_sim.datetime", _FakeClock):
        station = Station(env=env, spec=spec, publish=events.append)
        station.chargers[0].flaky = True
        env.process(station.vehicle_session())
        env.run(until=1000)

    occupied = [e for e in events if e["status"] == "occupied"]
    available = [e for e in events if e["status"] == "available"]
    assert len(occupied) == 1
    assert occupied[0]["last_verified_at"] == occupied[0]["reported_at"]

    final_available = available[-1]
    assert final_available["last_verified_at"] != final_available["reported_at"]
    assert final_available["last_verified_at"] == occupied[0]["reported_at"]


def test_non_flaky_charger_always_has_fresh_verification():
    spec = StationSpec("s-reliable", "public_dc_hub", "feeder-x", num_chargers=1, charger_power_kw=60.0)
    env = simpy.Environment()
    events = []
    random.seed(3)
    station = Station(env=env, spec=spec, publish=events.append)
    station.chargers[0].flaky = False
    env.process(station.vehicle_session())
    env.run(until=1000)

    for e in events:
        assert e["last_verified_at"] == e["reported_at"]
