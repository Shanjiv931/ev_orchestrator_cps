"""Seeds a realistic multi-city station network on first boot (only if the
`stations` table is empty) - the Section 8 `stations` table is otherwise
empty until a user or admin creates rows through the API, which would leave
the app's map looking broken out of the box for any city but the one the
simulation layer happens to model. This is presentation data for the map
and recommendation flow; it is independent of the live SUMO-driven
Bengaluru simulation from Phase 2, which continues to be the only city
with a real, live traffic-driven digital twin.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Charger, Station, SwapSlot


@dataclass(frozen=True)
class ChargerSpec:
    power_kw: float
    count: int = 1


@dataclass(frozen=True)
class StationSeed:
    city: str
    area: str
    station_type: str
    lat: float
    lon: float
    has_solar: bool
    safety_score: float
    chargers: list[ChargerSpec]
    swap_slots: int = 0


STATION_SEEDS: list[StationSeed] = [
    # --- Vellore (primary implementation city - see docs/out-of-scope.md) ---
    StationSeed("Vellore", "VIT University", "public_dc_hub", 12.9698, 79.1559, False, 0.88,
                [ChargerSpec(60.0, 4), ChargerSpec(120.0, 2)], swap_slots=6),
    StationSeed("Vellore", "Katpadi", "public_dc_hub", 12.9686, 79.1352, False, 0.8,
                [ChargerSpec(60.0, 3)]),
    StationSeed("Vellore", "CMC Hospital - Ida Scudder Road", "public_dc_hub", 12.9186, 79.1354, False, 0.85,
                [ChargerSpec(60.0, 3), ChargerSpec(120.0, 1)]),
    StationSeed("Vellore", "Vellore Fort", "housing_society_ac", 12.9202, 79.1329, True, 0.9,
                [ChargerSpec(7.4, 3)]),
    StationSeed("Vellore", "Bagayam", "housing_society_ac", 12.9401, 79.1204, True, 0.86,
                [ChargerSpec(7.4, 4)]),
    StationSeed("Vellore", "Sathuvachari", "housing_society_ac", 12.9004, 79.1284, False, 0.74,
                [ChargerSpec(7.4, 3)]),
    StationSeed("Vellore", "Gandhi Nagar", "public_dc_hub", 12.9235, 79.1450, False, 0.79,
                [ChargerSpec(60.0, 3)]),
    StationSeed("Vellore", "Thorapadi", "highway_corridor", 12.9550, 79.1180, False, 0.7,
                [ChargerSpec(120.0, 5)]),
    StationSeed("Vellore", "Officers Line", "housing_society_ac", 12.9150, 79.1370, True, 0.92,
                [ChargerSpec(7.4, 3)]),
    StationSeed("Vellore", "Chittoor Road", "highway_corridor", 12.9450, 79.1480, False, 0.68,
                [ChargerSpec(120.0, 4)], swap_slots=6),
    StationSeed("Vellore", "Green Circle", "public_dc_hub", 12.9280, 79.1395, False, 0.82,
                [ChargerSpec(60.0, 3)]),
    StationSeed("Vellore", "Arni Road", "highway_corridor", 12.9080, 79.1500, False, 0.72,
                [ChargerSpec(120.0, 4)]),
    # --- Bengaluru ---
    StationSeed("Bengaluru", "Koramangala", "public_dc_hub", 12.9352, 77.6146, False, 0.82,
                [ChargerSpec(60.0, 4), ChargerSpec(120.0, 2)], swap_slots=6),
    StationSeed("Bengaluru", "Indiranagar", "housing_society_ac", 12.9784, 77.6408, True, 0.9,
                [ChargerSpec(7.4, 4)]),
    StationSeed("Bengaluru", "Whitefield", "public_dc_hub", 12.9698, 77.7500, False, 0.75,
                [ChargerSpec(60.0, 3)]),
    # --- Mumbai ---
    StationSeed("Mumbai", "Bandra Kurla Complex", "public_dc_hub", 19.0662, 72.8686, False, 0.85,
                [ChargerSpec(120.0, 4)], swap_slots=8),
    StationSeed("Mumbai", "Andheri", "housing_society_ac", 19.1197, 72.8468, True, 0.7,
                [ChargerSpec(7.4, 3)]),
    StationSeed("Mumbai", "Powai", "public_dc_hub", 19.1176, 72.9060, False, 0.8,
                [ChargerSpec(60.0, 3)]),
    # --- Delhi NCR ---
    StationSeed("Delhi", "Connaught Place", "public_dc_hub", 28.6315, 77.2167, False, 0.78,
                [ChargerSpec(60.0, 4), ChargerSpec(120.0, 2)]),
    StationSeed("Delhi", "Dwarka", "housing_society_ac", 28.5921, 77.0460, True, 0.88,
                [ChargerSpec(7.4, 4)]),
    StationSeed("Delhi", "Saket", "public_dc_hub", 28.5245, 77.2066, False, 0.72,
                [ChargerSpec(60.0, 3)], swap_slots=6),
    # --- Chennai ---
    StationSeed("Chennai", "T Nagar", "public_dc_hub", 13.0418, 80.2341, False, 0.76,
                [ChargerSpec(60.0, 3)]),
    StationSeed("Chennai", "OMR", "highway_corridor", 12.8996, 80.2209, False, 0.68,
                [ChargerSpec(120.0, 6)]),
    StationSeed("Chennai", "Anna Nagar", "housing_society_ac", 13.0850, 80.2101, True, 0.9,
                [ChargerSpec(7.4, 3)]),
    # --- Hyderabad ---
    StationSeed("Hyderabad", "Hitech City", "public_dc_hub", 17.4483, 78.3915, False, 0.83,
                [ChargerSpec(60.0, 4), ChargerSpec(120.0, 2)], swap_slots=8),
    StationSeed("Hyderabad", "Banjara Hills", "housing_society_ac", 17.4156, 78.4347, True, 0.92,
                [ChargerSpec(7.4, 3)]),
    # --- Pune ---
    StationSeed("Pune", "Koregaon Park", "public_dc_hub", 18.5362, 73.8938, False, 0.8,
                [ChargerSpec(60.0, 3)]),
    StationSeed("Pune", "Hinjewadi", "highway_corridor", 18.5913, 73.7389, False, 0.7,
                [ChargerSpec(120.0, 5)]),
    # --- Kolkata ---
    StationSeed("Kolkata", "Salt Lake", "public_dc_hub", 22.5820, 88.4064, False, 0.77,
                [ChargerSpec(60.0, 3)], swap_slots=6),
    StationSeed("Kolkata", "Park Street", "housing_society_ac", 22.5527, 88.3520, True, 0.85,
                [ChargerSpec(7.4, 3)]),
]


def seed_stations_if_empty(db: Session) -> None:
    if db.query(Station).count() > 0:
        return

    for seed in STATION_SEEDS:
        station = Station(
            station_type=seed.station_type, lat=seed.lat, lon=seed.lon,
            safety_score=seed.safety_score, has_solar=seed.has_solar,
        )
        db.add(station)
        db.flush()  # get station.id before adding children

        for charger_spec in seed.chargers:
            for _ in range(charger_spec.count):
                db.add(Charger(station_id=station.id, status="available", power_kw=charger_spec.power_kw))

        if seed.swap_slots > 0:
            db.add(SwapSlot(station_id=station.id, status="available", batteries_available=seed.swap_slots))

    db.commit()
