import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import BatteryHealth, User, Vehicle
from app.schemas import BatteryHealthCreate, BatteryHealthRead

router = APIRouter(prefix="/vehicles/{vehicle_id}/battery-health", tags=["battery-health"])


def _get_owned_vehicle(vehicle_id: uuid.UUID, current_user: User, db: Session) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")
    return vehicle


@router.post("", response_model=BatteryHealthRead, status_code=status.HTTP_201_CREATED)
def record_battery_health(vehicle_id: uuid.UUID, payload: BatteryHealthCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BatteryHealth:
    _get_owned_vehicle(vehicle_id, current_user, db)
    record = BatteryHealth(vehicle_id=vehicle_id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[BatteryHealthRead])
def list_battery_health(vehicle_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[BatteryHealth]:
    _get_owned_vehicle(vehicle_id, current_user, db)
    return db.query(BatteryHealth).filter(BatteryHealth.vehicle_id == vehicle_id).order_by(BatteryHealth.recorded_at.desc()).all()


@router.get("/latest", response_model=BatteryHealthRead)
def latest_battery_health(vehicle_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BatteryHealth:
    _get_owned_vehicle(vehicle_id, current_user, db)
    record = (
        db.query(BatteryHealth)
        .filter(BatteryHealth.vehicle_id == vehicle_id)
        .order_by(BatteryHealth.recorded_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no battery health records yet")
    return record
