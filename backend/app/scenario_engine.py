"""Scenario presets for the Vellore simulation.

Each named scenario is a point in a small axis space (traffic / weather /
station availability / grid stress / fault-injection rate) rather than an
unrelated flat preset - this is what lets 8 named scenarios span a
meaningful range of real operating conditions instead of being 8 arbitrary
one-off configurations. Every axis besides station availability is
broadcast live over MQTT (`scenario/active`, retained) so the SUMO/
registry-driven simulation layer can react without a container restart:

- traffic         -> simulation/traci_bridge.py (per-vehicle SUMO speed factor)
- weather         -> simulation/traci_bridge.py (additional speed factor)
- grid_stress     -> simulation/grid_sim.py (synthetic extra feeder demand)
- fault_injection_rate -> simulation/charger_monitor_sim.py (fault probability)

Station availability still targets whichever real, DB-seeded station
(app/seed_stations.py) is nearest a configured real-world point - station
"names" like "VIT University" only exist at seed time and are never
persisted (see Station in models/entities.py), so presets key off (lat,
lon) instead of a name lookup. This touches chargers.status and
stations.queue_length - fields the frontend (StationDetailsPanel) already
renders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Charger, Station

# VIT University station (app/seed_stations.py) - the default scenario target.
DEFAULT_TARGET_LAT = 12.9698
DEFAULT_TARGET_LON = 79.1559


@dataclass(frozen=True)
class ScenarioPreset:
    id: str
    label: str
    description: str
    charger_status: str  # status every charger at the target station is set to
    queue_length: int
    traffic: str = "normal"  # normal | peak_surge | heavy_congestion
    weather: str = "clear"  # clear | rain | extreme_heat | fog
    grid_stress: str = "normal"  # normal | feeder_overload
    fault_injection_rate: str = "baseline"  # baseline | elevated


SCENARIOS: dict[str, ScenarioPreset] = {
    "normal": ScenarioPreset(
        "normal", "Normal day",
        "Light background traffic, station operating normally.",
        charger_status="available", queue_length=0,
    ),
    "station_shutdown": ScenarioPreset(
        "station_shutdown", "Station shut down",
        "The nearest station is offline - the app should reroute you to the next best one.",
        charger_status="offline", queue_length=0,
    ),
    "station_queued": ScenarioPreset(
        "station_queued", "6-8 cars waiting",
        "Every port is occupied and a queue has formed.",
        charger_status="occupied", queue_length=7,
    ),
    "station_degraded": ScenarioPreset(
        "station_degraded", "Station degraded",
        "Some ports are out of service, and the ones still running are more fault-prone.",
        charger_status="maintenance", queue_length=3,
        fault_injection_rate="elevated",
    ),
    "high_congestion": ScenarioPreset(
        "high_congestion", "Heavy traffic",
        "Dense background traffic and slower speeds along the route.",
        charger_status="available", queue_length=0,
        traffic="heavy_congestion",
    ),
    "monsoon_evening_rush": ScenarioPreset(
        "monsoon_evening_rush", "Monsoon evening rush",
        "Rain-slowed evening commute with a moderate charging queue as drivers plan around the weather.",
        charger_status="occupied", queue_length=2,
        traffic="peak_surge", weather="rain",
    ),
    "summer_heat_grid_stress": ScenarioPreset(
        "summer_heat_grid_stress", "Summer heat, grid under strain",
        "Extreme heat drives up AC load across the zone, stressing the feeder alongside EV charging demand.",
        charger_status="available", queue_length=0,
        weather="extreme_heat", grid_stress="feeder_overload", fault_injection_rate="elevated",
    ),
    "fog_morning": ScenarioPreset(
        "fog_morning", "Foggy morning commute",
        "Low visibility slows and bunches morning traffic.",
        charger_status="available", queue_length=0,
        traffic="peak_surge", weather="fog",
    ),
}


def find_nearest_station(db: Session, lat: float, lon: float) -> Station | None:
    stations = db.execute(select(Station)).scalars().all()
    if not stations:
        return None
    return min(stations, key=lambda s: math.dist((s.lat, s.lon), (lat, lon)))


def apply_scenario(
    db: Session, scenario_id: str, target_lat: float = DEFAULT_TARGET_LAT, target_lon: float = DEFAULT_TARGET_LON,
) -> tuple[ScenarioPreset, Station]:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario_id}")
    preset = SCENARIOS[scenario_id]

    station = find_nearest_station(db, target_lat, target_lon)
    if station is None:
        raise ValueError("no stations seeded - cannot apply scenario")

    for charger in db.execute(select(Charger).where(Charger.station_id == station.id)).scalars():
        charger.status = preset.charger_status
    station.queue_length = preset.queue_length
    db.commit()
    db.refresh(station)
    return preset, station
