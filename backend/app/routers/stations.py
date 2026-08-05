import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Charger, Station, SwapSlot, User
from app.schemas import (
    ChargerCreate,
    ChargerMaintenanceCheck,
    ChargerRead,
    ChargerUpdate,
    StationCreate,
    StationRead,
    StationUpdate,
    SwapSlotCreate,
    SwapSlotRead,
    SwapSlotUpdate,
)
from ml.maintenance_predictor import ChargerTelemetryWindow, compute_maintenance_risk_score

router = APIRouter(prefix="/stations", tags=["stations"])

RESERVATION_HOLD_MINUTES = 10


def _expire_stale_reservations(chargers: list[Charger], db: Session) -> None:
    """Lazy expiry on read rather than a background sweep job - nothing
    depends on a reservation's expiry firing at the exact moment it lapses,
    only on it being gone by the next time anyone looks."""
    now = datetime.now(timezone.utc)
    changed = False
    for charger in chargers:
        if charger.status == "reserved" and charger.reserved_until is not None and charger.reserved_until <= now:
            charger.status = "available"
            charger.reserved_until = None
            charger.reserved_by_user_id = None
            changed = True
    if changed:
        db.commit()


def _get_station(station_id: uuid.UUID, db: Session) -> Station:
    station = db.get(Station, station_id, options=[joinedload(Station.chargers), joinedload(Station.swap_slots)])
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="station not found")
    _expire_stale_reservations(station.chargers, db)
    return station


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(payload: StationCreate, db: Session = Depends(get_db)) -> Station:
    station = Station(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.get("", response_model=list[StationRead])
def list_stations(station_type: str | None = None, city: str | None = None, db: Session = Depends(get_db)) -> list[Station]:
    query = db.query(Station)
    if station_type is not None:
        query = query.filter(Station.station_type == station_type)
    if city is not None:
        query = query.filter(Station.city == city)
    stations = query.all()
    all_chargers = [c for s in stations for c in s.chargers]
    _expire_stale_reservations(all_chargers, db)
    return stations


@router.post("/{station_id}/reserve-any", response_model=ChargerRead)
def reserve_any_charger(station_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Charger:
    """Same "the app picks a port for you" philosophy as start-at-station -
    the caller shouldn't need to already know a specific charger_id."""
    station = _get_station(station_id, db)
    charger = (
        db.query(Charger)
        .filter(Charger.station_id == station_id, Charger.status == "available")
        .order_by(Charger.port_number)
        .first()
    )
    if charger is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no available charger at this station right now")
    charger.status = "reserved"
    charger.reserved_until = datetime.now(timezone.utc) + timedelta(minutes=RESERVATION_HOLD_MINUTES)
    charger.reserved_by_user_id = current_user.id
    db.commit()
    db.refresh(charger)
    return charger


@router.post("/chargers/{charger_id}/reserve", response_model=ChargerRead)
def reserve_charger(charger_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Charger:
    charger = db.get(Charger, charger_id)
    if charger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="charger not found")
    _expire_stale_reservations([charger], db)
    if charger.status != "available":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"charger is {charger.status}, not available")
    charger.status = "reserved"
    charger.reserved_until = datetime.now(timezone.utc) + timedelta(minutes=RESERVATION_HOLD_MINUTES)
    charger.reserved_by_user_id = current_user.id
    db.commit()
    db.refresh(charger)
    return charger


@router.post("/chargers/{charger_id}/cancel-reservation", response_model=ChargerRead)
def cancel_reservation(charger_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Charger:
    charger = db.get(Charger, charger_id)
    if charger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="charger not found")
    if charger.status == "reserved" and charger.reserved_by_user_id == current_user.id:
        charger.status = "available"
        charger.reserved_until = None
        charger.reserved_by_user_id = None
        db.commit()
        db.refresh(charger)
    return charger


@router.get("/{station_id}", response_model=StationRead)
def get_station(station_id: uuid.UUID, db: Session = Depends(get_db)) -> Station:
    return _get_station(station_id, db)


@router.patch("/{station_id}", response_model=StationRead)
def update_station(station_id: uuid.UUID, payload: StationUpdate, db: Session = Depends(get_db)) -> Station:
    station = _get_station(station_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(station, field, value)
    db.commit()
    db.refresh(station)
    return station


@router.post("/{station_id}/chargers", response_model=ChargerRead, status_code=status.HTTP_201_CREATED)
def create_charger(station_id: uuid.UUID, payload: ChargerCreate, db: Session = Depends(get_db)) -> Charger:
    _get_station(station_id, db)  # 404s if the station doesn't exist
    # Next port number for this station - chargers added one-off through this
    # endpoint (as opposed to app/seed_stations.py's bulk seeding) still need
    # one, or "go to port <n>" (app/routers/sessions.py's start-at-station)
    # would hand the user a None.
    highest = (
        db.query(Charger.port_number)
        .filter(Charger.station_id == station_id)
        .order_by(Charger.port_number.desc().nullslast())
        .first()
    )
    next_port = (highest[0] + 1) if highest and highest[0] is not None else 1
    charger = Charger(station_id=station_id, port_number=next_port, **payload.model_dump())
    db.add(charger)
    db.commit()
    db.refresh(charger)
    return charger


@router.patch("/chargers/{charger_id}", response_model=ChargerRead)
def update_charger(charger_id: uuid.UUID, payload: ChargerUpdate, db: Session = Depends(get_db)) -> Charger:
    charger = db.get(Charger, charger_id)
    if charger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="charger not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(charger, field, value)
    db.commit()
    db.refresh(charger)
    return charger


@router.post("/chargers/{charger_id}/maintenance-check", response_model=ChargerRead)
def run_maintenance_check(charger_id: uuid.UUID, payload: ChargerMaintenanceCheck, db: Session = Depends(get_db)) -> Charger:
    charger = db.get(Charger, charger_id)
    if charger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="charger not found")
    window = ChargerTelemetryWindow(
        charger_id=str(charger_id),
        total_sessions=payload.total_sessions,
        aborted_sessions=payload.aborted_sessions,
        error_count=payload.error_count,
    )
    charger.maintenance_risk_score = compute_maintenance_risk_score(window)
    db.commit()
    db.refresh(charger)
    return charger


@router.post("/{station_id}/swap-slots", response_model=SwapSlotRead, status_code=status.HTTP_201_CREATED)
def create_swap_slot(station_id: uuid.UUID, payload: SwapSlotCreate, db: Session = Depends(get_db)) -> SwapSlot:
    _get_station(station_id, db)
    swap_slot = SwapSlot(station_id=station_id, **payload.model_dump())
    db.add(swap_slot)
    db.commit()
    db.refresh(swap_slot)
    return swap_slot


@router.patch("/swap-slots/{swap_slot_id}", response_model=SwapSlotRead)
def update_swap_slot(swap_slot_id: uuid.UUID, payload: SwapSlotUpdate, db: Session = Depends(get_db)) -> SwapSlot:
    swap_slot = db.get(SwapSlot, swap_slot_id)
    if swap_slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="swap slot not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(swap_slot, field, value)
    db.commit()
    db.refresh(swap_slot)
    return swap_slot
