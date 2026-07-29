import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Charger, Station, SwapSlot
from app.schemas import (
    ChargerCreate,
    ChargerRead,
    ChargerUpdate,
    StationCreate,
    StationRead,
    StationUpdate,
    SwapSlotCreate,
    SwapSlotRead,
    SwapSlotUpdate,
)

router = APIRouter(prefix="/stations", tags=["stations"])


def _get_station(station_id: uuid.UUID, db: Session) -> Station:
    station = db.get(Station, station_id, options=[joinedload(Station.chargers), joinedload(Station.swap_slots)])
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="station not found")
    return station


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(payload: StationCreate, db: Session = Depends(get_db)) -> Station:
    station = Station(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.get("", response_model=list[StationRead])
def list_stations(station_type: str | None = None, db: Session = Depends(get_db)) -> list[Station]:
    query = db.query(Station)
    if station_type is not None:
        query = query.filter(Station.station_type == station_type)
    return query.all()


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
    charger = Charger(station_id=station_id, **payload.model_dump())
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
