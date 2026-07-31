"""Curated real Vellore points of interest (point 10: mall/hospital/idle-
parking geofencing) - the same "hand-curated real-world data, no live third-
party geocoding dependency" pattern already used for stations
(app/seed_stations.py) and the vehicle catalog (app/vehicle_catalog.py).
Coordinates are deliberately reused from existing Vellore station seeds
where the two really are the same place (e.g. CMC Hospital), so "chargers
available here" is never fabricated - see app/routers/poi.py, which computes
that count live from the real stations table rather than storing a number
here that could drift out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PoiSeed:
    name: str
    poi_type: str  # "mall" | "hospital" | "idle_parking"
    lat: float
    lon: float


POI_SEEDS: list[PoiSeed] = [
    # Same coordinates as the CMC Hospital station seed - genuinely the same site.
    PoiSeed("CMC Hospital - Ida Scudder Road", "hospital", 12.9186, 79.1354),
    PoiSeed("Vellore Fort Shopping Complex", "mall", 12.9202, 79.1329),
    PoiSeed("VIT University Campus", "idle_parking", 12.9698, 79.1559),
    PoiSeed("Green Circle Market", "mall", 12.9280, 79.1395),
    PoiSeed("Bagayam Residential Parking", "idle_parking", 12.9401, 79.1204),
    # No charging station nearby - exercises the "no chargers here" default path.
    PoiSeed("Sathuvachari Community Hall", "idle_parking", 12.9004, 79.1284),
]
