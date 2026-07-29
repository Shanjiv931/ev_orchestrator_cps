from ml.blackout_resilience import CriticalLoad, plan_emergency_backup
from ml.v2g_dispatch import V2GVehicle


def _vehicle(**overrides) -> V2GVehicle:
    defaults = dict(
        id="v1", is_pluggable=True, v2g_capable=True, opted_in=True, is_parked=True,
        soc_pct=85.0, battery_capacity_kwh=60.0, max_discharge_kw=7.0,
    )
    defaults.update(overrides)
    return V2GVehicle(**defaults)


def test_far_away_vehicles_are_excluded_from_the_backup_plan():
    clinic = CriticalLoad(id="clinic-1", name="Test Clinic", lat=12.935, lon=77.615, required_kw=10.0)
    nearby = _vehicle(id="near")
    far = _vehicle(id="far")
    positions = {"near": (12.936, 77.616), "far": (13.200, 78.000)}

    plan = plan_emergency_backup(clinic, [nearby, far], positions, max_radius_km=3.0)
    covered_ids = {a.vehicle_id for a in plan.allocations}
    assert "near" in covered_ids
    assert "far" not in covered_ids


def test_coverage_ratio_reflects_partial_vs_full_coverage():
    clinic = CriticalLoad(id="clinic-2", name="Big Clinic", lat=12.935, lon=77.615, required_kw=100.0)
    one_small_vehicle = _vehicle(id="v1", max_discharge_kw=5.0)
    positions = {"v1": (12.935, 77.615)}

    plan = plan_emergency_backup(clinic, [one_small_vehicle], positions)
    assert plan.coverage_ratio < 1.0

    clinic_small = CriticalLoad(id="clinic-3", name="Small Clinic", lat=12.935, lon=77.615, required_kw=2.0)
    plan_full = plan_emergency_backup(clinic_small, [one_small_vehicle], positions)
    assert plan_full.coverage_ratio == 1.0


def test_no_eligible_vehicles_yields_zero_coverage():
    clinic = CriticalLoad(id="clinic-4", name="Isolated Clinic", lat=12.935, lon=77.615, required_kw=10.0)
    not_opted_in = _vehicle(id="v1", opted_in=False)
    positions = {"v1": (12.935, 77.615)}

    plan = plan_emergency_backup(clinic, [not_opted_in], positions)
    assert plan.allocations == []
    assert plan.total_available_kw == 0.0
    assert plan.coverage_ratio == 0.0
