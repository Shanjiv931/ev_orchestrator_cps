import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Vehicle
from app.schemas import VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _get_owned_vehicle(vehicle_id: uuid.UUID, current_user: User, db: Session) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")
    return vehicle


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Vehicle:
    vehicle = Vehicle(user_id=current_user.id, **payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("", response_model=list[VehicleRead])
def list_my_vehicles(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Vehicle]:
    return db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Vehicle:
    return _get_owned_vehicle(vehicle_id, current_user, db)


@router.patch("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(vehicle_id: uuid.UUID, payload: VehicleUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Vehicle:
    vehicle = _get_owned_vehicle(vehicle_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    vehicle = _get_owned_vehicle(vehicle_id, current_user, db)
    db.delete(vehicle)
    db.commit()
