"""Fleet depot scheduler (Section 4.5.5).

A genuinely different problem from the single-user recommender: a joint
batch assignment of N depot vehicles to M chargers over a shared overnight
window, minimizing total fleet downtime AND peak simultaneous grid draw
together. Built on OR-Tools CP-SAT interval variables (`NewOptionalIntervalVar`
+ `AddNoOverlap` per charger, `AddCumulative` for the shared feeder limit) -
a scheduling formulation with no analogue in `recommendation.py`'s per-request
weighted scoring, not a loop wrapped around it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ortools.sat.python import cp_model

UNSERVED_PENALTY_SLOTS = 1000  # dominates: always prefer serving a vehicle over leaving it unserved
PEAK_DRAW_WEIGHT = 1


@dataclass
class DepotVehicle:
    id: str
    energy_needed_kwh: float
    is_emergency_priority: bool = False


@dataclass
class DepotCharger:
    id: str
    power_kw: float


@dataclass
class VehicleAssignment:
    vehicle_id: str
    charger_id: str | None
    start_slot: int | None
    required_slots: int | None


@dataclass
class ScheduleResult:
    assignments: list[VehicleAssignment]
    peak_draw_kw: float
    total_downtime_slots: int
    served_count: int


def _required_slots(vehicle: DepotVehicle, charger: DepotCharger, slot_hours: float) -> int:
    hours_needed = vehicle.energy_needed_kwh / charger.power_kw
    return max(1, math.ceil(hours_needed / slot_hours))


def schedule_fleet(vehicles: list[DepotVehicle], chargers: list[DepotCharger], horizon_slots: int = 8,
                    slot_hours: float = 1.0, feeder_capacity_kw: float | None = None) -> ScheduleResult:
    model = cp_model.CpModel()

    presence: dict[tuple[str, str], cp_model.IntVar] = {}
    starts: dict[tuple[str, str], cp_model.IntVar] = {}
    intervals = []
    demands = []

    for vehicle in vehicles:
        vehicle_presence_vars = []
        for charger in chargers:
            slots_needed = _required_slots(vehicle, charger, slot_hours)
            if slots_needed > horizon_slots:
                continue  # this charger can't finish the job within the window at all
            key = (vehicle.id, charger.id)
            is_present = model.NewBoolVar(f"assign_{vehicle.id}_{charger.id}")
            start = model.NewIntVar(0, horizon_slots - slots_needed, f"start_{vehicle.id}_{charger.id}")
            interval = model.NewOptionalIntervalVar(start, slots_needed, start + slots_needed, is_present,
                                                      f"interval_{vehicle.id}_{charger.id}")
            presence[key] = is_present
            starts[key] = start
            vehicle_presence_vars.append(is_present)
            intervals.append((charger.id, interval, charger.power_kw, is_present))

        model.Add(sum(vehicle_presence_vars) <= 1)  # at most one charger per vehicle

    for charger in chargers:
        charger_intervals = [iv for cid, iv, _p, _pr in intervals if cid == charger.id]
        model.AddNoOverlap(charger_intervals)

    peak_draw = model.NewIntVar(0, int(sum(c.power_kw for c in chargers)) + 1, "peak_draw_kw")
    if intervals:
        model.AddCumulative(
            [iv for _cid, iv, _p, _pr in intervals],
            [int(power) for _cid, _iv, power, _pr in intervals],
            peak_draw,
        )
    else:
        model.Add(peak_draw == 0)
    if feeder_capacity_kw is not None:
        model.Add(peak_draw <= int(feeder_capacity_kw))

    downtime_terms = []
    for vehicle in vehicles:
        served_terms = []
        for charger in chargers:
            key = (vehicle.id, charger.id)
            if key not in presence:
                continue
            slots_needed = _required_slots(vehicle, charger, slot_hours)
            downtime_terms.append(slots_needed * presence[key])
            served_terms.append(presence[key])
        priority_weight = 3 if vehicle.is_emergency_priority else 1
        if served_terms:
            downtime_terms.append(priority_weight * UNSERVED_PENALTY_SLOTS * (1 - sum(served_terms)))
        else:
            downtime_terms.append(priority_weight * UNSERVED_PENALTY_SLOTS)

    total_downtime = sum(downtime_terms)
    model.Minimize(total_downtime * 10 + PEAK_DRAW_WEIGHT * peak_draw)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"fleet scheduling failed: solver status {status}")

    assignments = []
    served_count = 0
    downtime_total = 0
    for vehicle in vehicles:
        assigned_charger = None
        assigned_start = None
        assigned_slots = None
        for charger in chargers:
            key = (vehicle.id, charger.id)
            if key in presence and solver.Value(presence[key]) == 1:
                assigned_charger = charger.id
                assigned_start = solver.Value(starts[key])
                assigned_slots = _required_slots(vehicle, charger, slot_hours)
                served_count += 1
                downtime_total += assigned_slots
                break
        assignments.append(VehicleAssignment(
            vehicle_id=vehicle.id, charger_id=assigned_charger,
            start_slot=assigned_start, required_slots=assigned_slots,
        ))

    return ScheduleResult(
        assignments=assignments,
        peak_draw_kw=float(solver.Value(peak_draw)),
        total_downtime_slots=downtime_total,
        served_count=served_count,
    )


def naive_independent_assignment(vehicles: list[DepotVehicle], chargers: list[DepotCharger],
                                  horizon_slots: int = 8, slot_hours: float = 1.0) -> ScheduleResult:
    """What 'looping the single-user recommender N times' looks like: each
    vehicle independently grabs whichever charger frees up soonest, exactly
    like a real per-vehicle recommendation query against live charger
    status - but with zero awareness of the *other* vehicles being
    scheduled in the same batch, and critically, no awareness of the
    shared feeder's total capacity. It can and does overload the feeder
    when enough vehicles arrive at once; the joint scheduler treats that
    as a hard constraint instead."""
    charger_next_free_slot = {c.id: 0 for c in chargers}
    assignments = []
    served_count = 0
    downtime_total = 0
    occupancy: dict[int, float] = {s: 0.0 for s in range(horizon_slots)}

    for vehicle in vehicles:
        best_charger = min(chargers, key=lambda c: charger_next_free_slot[c.id])
        slots_needed = _required_slots(vehicle, best_charger, slot_hours)
        start = charger_next_free_slot[best_charger.id]
        if start + slots_needed > horizon_slots:
            assignments.append(VehicleAssignment(vehicle.id, None, None, None))
            continue
        charger_next_free_slot[best_charger.id] = start + slots_needed
        for s in range(start, start + slots_needed):
            occupancy[s] += best_charger.power_kw
        assignments.append(VehicleAssignment(vehicle.id, best_charger.id, start, slots_needed))
        served_count += 1
        downtime_total += slots_needed

    return ScheduleResult(
        assignments=assignments,
        peak_draw_kw=max(occupancy.values()) if occupancy else 0.0,
        total_downtime_slots=downtime_total,
        served_count=served_count,
    )
