import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traci_bridge import VEHICLE_CLASSES, VehicleProfile, build_profile, deplete_battery


def test_build_profile_is_deterministic_for_same_vehicle_id():
    p1 = build_profile("veh42")
    p2 = build_profile("veh42")
    assert p1 == p2


def test_build_profile_assigns_a_known_vehicle_class():
    profile = build_profile("veh1")
    assert profile.vehicle_class in VEHICLE_CLASSES


def test_build_profile_connector_matches_vehicle_class_family():
    for vehicle_id in [f"veh{i}" for i in range(50)]:
        profile = build_profile(vehicle_id)
        if profile.vehicle_class == "4W":
            assert profile.connector_type in {"Bharat DC-001", "CCS2", "Type 2"}
        else:
            assert profile.connector_type in {"swap-cassette", "Bharat AC-001"}


def test_most_vehicles_are_pluggable_but_some_are_not():
    """Non-plug-in hybrids must be a distinguishable minority, not silently
    mismatched into the plug-in fleet (Section 4.1)."""
    profiles = [build_profile(f"veh{i}") for i in range(500)]
    pluggable = sum(1 for p in profiles if p.is_pluggable)
    non_pluggable = len(profiles) - pluggable
    assert non_pluggable > 0
    assert pluggable / len(profiles) > 0.8


def test_deplete_battery_reduces_percentage_proportional_to_energy_used():
    profile = VehicleProfile(
        vehicle_class="4W", connector_type="CCS2", battery_chemistry="NMC",
        is_pluggable=True, battery_capacity_kwh=40.0, consumption_kwh_per_km=0.15,
        battery_pct=100.0,
    )
    deplete_battery(profile, distance_km=100.0)
    # 100km * 0.15 kWh/km = 15 kWh used out of 40 kWh capacity = 37.5%
    assert profile.battery_pct == 62.5


def test_deplete_battery_never_goes_negative():
    profile = VehicleProfile(
        vehicle_class="2W", connector_type="Bharat AC-001", battery_chemistry="LFP",
        is_pluggable=True, battery_capacity_kwh=3.0, consumption_kwh_per_km=0.03,
        battery_pct=5.0,
    )
    deplete_battery(profile, distance_km=1000.0)
    assert profile.battery_pct == 0.0
