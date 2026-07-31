import math

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Station, User
from app.poi_data import POI_SEEDS
from app.schemas import PoiRead

router = APIRouter(prefix="/poi", tags=["poi"])

# A station counts as "at" a POI within this radius - Vellore's stations
# are spread across town, so this is tight enough that "chargers available
# here" means the same physical site, not just "somewhere nearby in Vellore".
NEARBY_RADIUS_KM = 0.3


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@router.get("", response_model=list[PoiRead])
def list_pois(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[PoiRead]:
    """Vellore malls/hospitals/idle-parking spots (see app/poi_data.py), each
    paired with whichever real station sits at that site (if any) and how
    many of its chargers are free right now - computed live so this can
    never drift out of sync with actual charger status."""
    stations = db.query(Station).all()
    results: list[PoiRead] = []
    for poi in POI_SEEDS:
        nearest = min(
            (s for s in stations if _haversine_km(poi.lat, poi.lon, s.lat, s.lon) <= NEARBY_RADIUS_KM),
            key=lambda s: _haversine_km(poi.lat, poi.lon, s.lat, s.lon),
            default=None,
        )
        available = sum(1 for c in nearest.chargers if c.status == "available") if nearest else 0
        results.append(PoiRead(
            name=poi.name, poi_type=poi.poi_type, lat=poi.lat, lon=poi.lon,
            nearby_station_id=nearest.id if nearest else None,
            nearby_available_chargers=available,
        ))
    return results
