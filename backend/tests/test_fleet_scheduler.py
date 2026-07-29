from ml.fleet_scheduler import DepotCharger, DepotVehicle, naive_independent_assignment, schedule_fleet


def _six_vehicles_three_chargers():
    vehicles = [DepotVehicle(id=f"v{i}", energy_needed_kwh=40.0) for i in range(6)]
    chargers = [DepotCharger(id=f"c{i}", power_kw=20.0) for i in range(3)]
    return vehicles, chargers


def test_no_session_extends_past_the_depot_operating_window():
    vehicles, chargers = _six_vehicles_three_chargers()
    result = schedule_fleet(vehicles, chargers, horizon_slots=8, slot_hours=1.0)
    for a in result.assignments:
        if a.start_slot is not None:
            assert a.start_slot + a.required_slots <= 8


def test_joint_scheduler_achieves_lower_peak_draw_than_naive_at_equal_service_level():
    """Section 11's acceptance test: output must differ meaningfully from
    looping the single-user recommender. Same vehicles, same chargers, same
    number served and same total downtime - but the joint scheduler
    staggers sessions to cut peak simultaneous draw, where the naive
    per-vehicle-independent loop just grabs the soonest-free charger with
    no awareness of what else is running at the same time."""
    vehicles, chargers = _six_vehicles_three_chargers()
    joint = schedule_fleet(vehicles, chargers, horizon_slots=8, slot_hours=1.0)
    naive = naive_independent_assignment(vehicles, chargers, horizon_slots=8, slot_hours=1.0)

    assert joint.served_count == naive.served_count == 6
    assert joint.total_downtime_slots == naive.total_downtime_slots
    assert joint.peak_draw_kw < naive.peak_draw_kw


def test_joint_scheduler_respects_feeder_capacity_naive_would_violate():
    vehicles, chargers = _six_vehicles_three_chargers()
    naive = naive_independent_assignment(vehicles, chargers, horizon_slots=8, slot_hours=1.0)
    feeder_cap = 40.0

    assert naive.peak_draw_kw > feeder_cap  # confirms naive really would overload this feeder

    joint = schedule_fleet(vehicles, chargers, horizon_slots=8, slot_hours=1.0, feeder_capacity_kw=feeder_cap)
    assert joint.peak_draw_kw <= feeder_cap
    assert joint.served_count == 6  # still serves everyone, just staggered


def test_emergency_priority_vehicle_served_over_regular_vehicles_under_scarce_capacity():
    vehicles = [DepotVehicle(id=f"v{i}", energy_needed_kwh=80.0) for i in range(4)]
    vehicles.append(DepotVehicle(id="v-emergency", energy_needed_kwh=80.0, is_emergency_priority=True))
    chargers = [DepotCharger(id="c0", power_kw=20.0)]  # only one charger: not everyone fits

    result = schedule_fleet(vehicles, chargers, horizon_slots=8, slot_hours=1.0)
    served_ids = {a.vehicle_id for a in result.assignments if a.charger_id is not None}
    assert "v-emergency" in served_ids


def test_scheduler_is_not_a_thin_wrapper_around_the_recommender():
    """Structural guard: the fleet scheduler must not import the single-user
    recommendation scorer at all - it's a genuinely different joint
    optimization (interval scheduling), not recommendation.py looped N
    times over independent per-vehicle calls."""
    import ast

    import ml.fleet_scheduler as fleet_scheduler_module

    with open(fleet_scheduler_module.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert not any("recommendation" in name for name in imported_modules)
