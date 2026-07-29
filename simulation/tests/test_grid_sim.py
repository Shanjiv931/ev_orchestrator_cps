import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grid_sim import Feeder, FeederLoadAggregator
from registry import FeederSpec


def test_feeder_reports_low_loading_under_light_draw():
    feeder = Feeder(FeederSpec("f1", "test-zone", capacity_kw=100.0))
    reading = feeder.step(load_kw=10.0)
    assert reading["current_load_kw"] == 10.0
    assert 0 < reading["loading_percent"] < 50
    assert reading["is_overloaded"] is False


def test_feeder_flags_overload_past_capacity():
    feeder = Feeder(FeederSpec("f2", "test-zone", capacity_kw=50.0))
    reading = feeder.step(load_kw=90.0)
    assert reading["loading_percent"] > 100.0
    assert reading["is_overloaded"] is True


def test_two_feeders_are_independent():
    """A single local transformer overloading must not affect a sibling feeder."""
    housing = Feeder(FeederSpec("housing", "housing-zone", capacity_kw=50.0))
    dc_hub = Feeder(FeederSpec("dc-hub", "dc-hub-zone", capacity_kw=1000.0))

    housing_reading = housing.step(load_kw=95.0)
    dc_hub_reading = dc_hub.step(load_kw=200.0)

    assert housing_reading["is_overloaded"] is True
    assert dc_hub_reading["is_overloaded"] is False


def test_rural_minigrid_has_low_capacity_ceiling():
    minigrid = Feeder(FeederSpec("rural-1", "rural-zone", capacity_kw=25.0, is_rural_minigrid=True))
    reading = minigrid.step(load_kw=20.0)
    assert reading["is_rural_minigrid"] is True
    assert reading["loading_percent"] > 50


def test_aggregator_sums_only_matching_feeder():
    aggregator = FeederLoadAggregator()
    aggregator.update("charger-1", "feeder-a", 60.0)
    aggregator.update("charger-2", "feeder-a", 30.0)
    aggregator.update("charger-3", "feeder-b", 120.0)

    assert aggregator.total_for_feeder("feeder-a") == 90.0
    assert aggregator.total_for_feeder("feeder-b") == 120.0
    assert aggregator.total_for_feeder("feeder-c") == 0.0


def test_aggregator_reflects_charger_going_idle():
    aggregator = FeederLoadAggregator()
    aggregator.update("charger-1", "feeder-a", 60.0)
    assert aggregator.total_for_feeder("feeder-a") == 60.0
    aggregator.update("charger-1", "feeder-a", 0.0)
    assert aggregator.total_for_feeder("feeder-a") == 0.0
