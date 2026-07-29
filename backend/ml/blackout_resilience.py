"""Blackout resilience mode (Section 5.2).

During a simulated feeder outage, recommends nearby opt-in, V2H-capable EVs
as emergency backup power for a tagged critical load (a clinic, a housing
society's essential circuit) - an admin-triggerable disaster scenario built
directly on top of v2g_dispatch's eligibility/allocation logic, since
"discharge a parked EV to cover a power deficit" is the same underlying
mechanism whether the deficit is a grid peak or an actual outage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ml.v2g_dispatch import V2GVehicle, dispatch_v2g


@dataclass
class CriticalLoad:
    id: str
    name: str  # e.g. "Koramangala Clinic"
    lat: float
    lon: float
    required_kw: float


@dataclass
class BackupPlan:
    critical_load_id: str
    allocations: list
    total_available_kw: float
    coverage_ratio: float  # 1.0 = fully covered, <1.0 = partial


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def plan_emergency_backup(critical_load: CriticalLoad, candidate_vehicles: list[V2GVehicle],
                           vehicle_positions: dict[str, tuple[float, float]],
                           max_radius_km: float = 3.0, duration_hours: float = 2.0) -> BackupPlan:
    nearby = [
        v for v in candidate_vehicles
        if v.id in vehicle_positions
        and _haversine_km(critical_load.lat, critical_load.lon, *vehicle_positions[v.id]) <= max_radius_km
    ]
    allocations = dispatch_v2g(nearby, feeder_deficit_kw=critical_load.required_kw, duration_hours=duration_hours)
    total_available_kw = sum(a.discharge_kw for a in allocations)
    coverage_ratio = min(1.0, total_available_kw / critical_load.required_kw) if critical_load.required_kw > 0 else 1.0
    return BackupPlan(
        critical_load_id=critical_load.id,
        allocations=allocations,
        total_available_kw=round(total_available_kw, 2),
        coverage_ratio=round(coverage_ratio, 3),
    )
