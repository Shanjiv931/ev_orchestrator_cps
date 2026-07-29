"""Vehicle-to-Grid / Vehicle-to-Home dispatch (Section 5.1).

Turns a slice of parked, sufficiently-charged, opt-in EVs into a
distributed grid asset during a feeder peak event: selects eligible
vehicles, allocates discharge power across them to help cover a feeder's
power deficit (capped by each vehicle's own reserve and discharge limit),
and computes the incentive payment the owner would receive.
"""
from __future__ import annotations

from dataclasses import dataclass

RESERVE_SOC_PCT = 30.0  # never discharge below this - keeps a usable reserve for the owner
DEFAULT_INCENTIVE_RUPEES_PER_KWH = 8.0  # a premium over typical retail tariff, to incentivize participation


@dataclass
class V2GVehicle:
    id: str
    is_pluggable: bool
    v2g_capable: bool
    opted_in: bool
    is_parked: bool
    soc_pct: float
    battery_capacity_kwh: float
    max_discharge_kw: float


@dataclass
class V2GAllocation:
    vehicle_id: str
    discharge_kw: float
    duration_hours: float
    energy_discharged_kwh: float
    incentive_rupees: float


def is_v2g_eligible(vehicle: V2GVehicle) -> bool:
    return (
        vehicle.is_pluggable
        and vehicle.v2g_capable
        and vehicle.opted_in
        and vehicle.is_parked
        and vehicle.soc_pct > RESERVE_SOC_PCT
    )


def select_v2g_candidates(vehicles: list[V2GVehicle]) -> list[V2GVehicle]:
    return [v for v in vehicles if is_v2g_eligible(v)]


def dispatch_v2g(vehicles: list[V2GVehicle], feeder_deficit_kw: float, duration_hours: float = 1.0,
                  incentive_rupees_per_kwh: float = DEFAULT_INCENTIVE_RUPEES_PER_KWH) -> list[V2GAllocation]:
    """Allocates discharge across eligible vehicles, proportional to each
    vehicle's available energy above its reserve, until the deficit is
    covered or every eligible vehicle is fully tapped."""
    candidates = select_v2g_candidates(vehicles)
    remaining_deficit_kw = feeder_deficit_kw
    allocations = []

    for vehicle in sorted(candidates, key=lambda v: v.soc_pct, reverse=True):
        if remaining_deficit_kw <= 0:
            break
        available_kwh = (vehicle.soc_pct - RESERVE_SOC_PCT) / 100.0 * vehicle.battery_capacity_kwh
        max_kw_from_energy = available_kwh / duration_hours if duration_hours > 0 else 0.0
        discharge_kw = min(vehicle.max_discharge_kw, max_kw_from_energy, remaining_deficit_kw)
        if discharge_kw <= 0:
            continue
        energy_kwh = discharge_kw * duration_hours
        allocations.append(V2GAllocation(
            vehicle_id=vehicle.id,
            discharge_kw=round(discharge_kw, 2),
            duration_hours=duration_hours,
            energy_discharged_kwh=round(energy_kwh, 3),
            incentive_rupees=round(energy_kwh * incentive_rupees_per_kwh, 2),
        ))
        remaining_deficit_kw -= discharge_kw

    return allocations
