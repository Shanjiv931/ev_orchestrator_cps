import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CarbonLedgerEntry, Charger, ChargingBehaviorLog, ChargingSession, Station, Telemetry, User, Vehicle
from app.schemas import (
    SessionCreate,
    SessionRead,
    SessionUpdate,
    SessionWithPortRead,
    StartSessionAtStationRequest,
    TelemetryCreate,
    TelemetryRead,
)
from ml.carbon_ledger import compute_carbon_impact
from ml.demand_forecast import ZONES

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Real ground truth for the demand-forecast model (point 13) reuses the same
# zone categories ml/demand_forecast.py already models - a station's own
# station_type doubles as its zone, and home charging (no public station at
# all) is inherently the residential zone.
_STATION_TYPE_TO_ZONE = {
    "public_dc_hub": ZONES[0],
    "housing_society_ac": ZONES[1],
    "highway_corridor": ZONES[2],
}
_HOME_CHARGING_ZONE = ZONES[3]


def _zone_for_session(session: ChargingSession, db: Session) -> str | None:
    if session.home_charger_id is not None:
        return _HOME_CHARGING_ZONE
    if session.charger_id is not None:
        charger = db.get(Charger, session.charger_id)
        if charger is not None:
            station = db.get(Station, charger.station_id)
            if station is not None:
                return _STATION_TYPE_TO_ZONE.get(station.station_type)
    return None


def _get_owned_session(session_id: uuid.UUID, current_user: User, db: Session) -> ChargingSession:
    session = db.get(ChargingSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def start_session(payload: SessionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChargingSession:
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")
    session = ChargingSession(user_id=current_user.id, **payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/start-at-station", response_model=SessionWithPortRead, status_code=status.HTTP_201_CREATED)
def start_session_at_station(
    payload: StartSessionAtStationRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> SessionWithPortRead:
    """The "find best station" flow's conclusion: once the user has
    physically arrived, this picks an available charger at that station
    (lowest port_number first, for a stable/predictable assignment) and
    hands back which port to go to - the whole point being the user
    shouldn't have to guess or ask an attendant which one is free."""
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")

    # A port this user reserved (POST /stations/chargers/{id}/reserve) takes
    # priority over "just pick the first free one" - otherwise the specific
    # port they were told to walk to could get handed to someone else's
    # session instead, defeating the point of holding it.
    charger = (
        db.query(Charger)
        .filter(Charger.station_id == payload.station_id, Charger.status == "reserved",
                Charger.reserved_by_user_id == current_user.id)
        .order_by(Charger.port_number)
        .first()
    )
    if charger is None:
        charger = (
            db.query(Charger)
            .filter(Charger.station_id == payload.station_id, Charger.status == "available")
            .order_by(Charger.port_number)
            .first()
        )
    if charger is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no available charger at this station right now")

    charger.status = "occupied"
    charger.reserved_until = None
    charger.reserved_by_user_id = None
    session = ChargingSession(user_id=current_user.id, vehicle_id=payload.vehicle_id, charger_id=charger.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionWithPortRead(**SessionRead.model_validate(session).model_dump(), port_number=charger.port_number)


@router.get("", response_model=list[SessionRead])
def list_my_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChargingSession]:
    return db.query(ChargingSession).filter(ChargingSession.user_id == current_user.id).all()


@router.get("/{session_id}", response_model=SessionRead)
def get_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChargingSession:
    return _get_owned_session(session_id, current_user, db)


@router.patch("/{session_id}", response_model=SessionRead)
def update_session(session_id: uuid.UUID, payload: SessionUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChargingSession:
    session = _get_owned_session(session_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/complete", response_model=SessionRead)
def complete_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChargingSession:
    session = _get_owned_session(session_id, current_user, db)
    session.end_time = datetime.now(timezone.utc)

    # Release the port - without this, every charger ever assigned via
    # start-at-station stays "occupied" forever after its first use, and
    # the whole point of port assignment (finding one that's actually free)
    # breaks for the next person.
    if session.charger_id is not None:
        charger = db.get(Charger, session.charger_id)
        if charger is not None:
            charger.status = "available"

    if session.energy_kwh > 0:
        vehicle = db.get(Vehicle, session.vehicle_id)
        impact = compute_carbon_impact(session.energy_kwh, vehicle.vehicle_class)
        db.add(CarbonLedgerEntry(
            session_id=session.id,
            co2_avoided_kg=impact.co2_avoided_kg,
            equivalent_fuel_baseline=impact.equivalent_fuel_baseline,
        ))

    zone = _zone_for_session(session, db)
    if zone is not None:
        db.add(ChargingBehaviorLog(
            session_id=session.id, user_id=session.user_id, zone=zone,
            hour=session.start_time.hour, day_of_week=session.start_time.weekday(),
            energy_kwh=session.energy_kwh, is_emergency_priority=session.is_emergency_priority,
        ))

    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/telemetry", response_model=TelemetryRead, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(session_id: uuid.UUID, payload: TelemetryCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Telemetry:
    _get_owned_session(session_id, current_user, db)
    telemetry = Telemetry(session_id=session_id, **payload.model_dump())
    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)
    return telemetry


@router.get("/{session_id}/telemetry", response_model=list[TelemetryRead])
def list_telemetry(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Telemetry]:
    _get_owned_session(session_id, current_user, db)
    return db.query(Telemetry).filter(Telemetry.session_id == session_id).order_by(Telemetry.ts).all()
