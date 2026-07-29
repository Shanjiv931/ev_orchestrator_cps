from ml.v2g_dispatch import V2GVehicle, dispatch_v2g, select_v2g_candidates


def _vehicle(**overrides) -> V2GVehicle:
    defaults = dict(
        id="v1", is_pluggable=True, v2g_capable=True, opted_in=True, is_parked=True,
        soc_pct=80.0, battery_capacity_kwh=60.0, max_discharge_kw=7.0,
    )
    defaults.update(overrides)
    return V2GVehicle(**defaults)


def test_non_opted_in_vehicle_is_excluded():
    vehicles = [_vehicle(id="a", opted_in=False)]
    assert select_v2g_candidates(vehicles) == []


def test_vehicle_below_reserve_soc_is_excluded():
    vehicles = [_vehicle(id="a", soc_pct=25.0)]
    assert select_v2g_candidates(vehicles) == []


def test_non_v2g_capable_or_not_parked_vehicles_excluded():
    assert select_v2g_candidates([_vehicle(id="a", v2g_capable=False)]) == []
    assert select_v2g_candidates([_vehicle(id="a", is_parked=False)]) == []


def test_dispatch_covers_feeder_deficit_from_eligible_vehicles():
    vehicles = [_vehicle(id="a", soc_pct=90.0), _vehicle(id="b", soc_pct=85.0)]
    allocations = dispatch_v2g(vehicles, feeder_deficit_kw=10.0, duration_hours=1.0)
    total_kw = sum(a.discharge_kw for a in allocations)
    assert total_kw <= 10.0 + 1e-6
    assert total_kw > 0


def test_dispatch_never_exceeds_a_vehicles_max_discharge_rate():
    vehicles = [_vehicle(id="a", soc_pct=95.0, max_discharge_kw=5.0, battery_capacity_kwh=100.0)]
    allocations = dispatch_v2g(vehicles, feeder_deficit_kw=50.0, duration_hours=1.0)
    assert allocations[0].discharge_kw <= 5.0


def test_incentive_scales_with_energy_discharged():
    vehicles = [_vehicle(id="a", soc_pct=90.0, max_discharge_kw=7.0, battery_capacity_kwh=60.0)]
    allocations = dispatch_v2g(vehicles, feeder_deficit_kw=100.0, duration_hours=2.0, incentive_rupees_per_kwh=10.0)
    allocation = allocations[0]
    assert allocation.incentive_rupees == round(allocation.energy_discharged_kwh * 10.0, 2)


def test_ineligible_vehicles_receive_no_allocation():
    vehicles = [_vehicle(id="a", opted_in=False), _vehicle(id="b", soc_pct=90.0)]
    allocations = dispatch_v2g(vehicles, feeder_deficit_kw=5.0)
    assert {a.vehicle_id for a in allocations} == {"b"}
