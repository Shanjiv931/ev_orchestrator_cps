import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import MeridianGridProvisioning, User, Vehicle, VehicleRequest
from app.schemas import (
    MeridianGridLookupResponse,
    VehicleAddRequestCreate,
    VehicleDeleteRequestCreate,
    VehicleRead,
    VehicleRequestRead,
    VehicleUpdate,
)
from app.vellore import DELETE_REASON_CODES, generate_ticket_code, is_vellore_plate, normalize_plate

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _get_owned_vehicle(vehicle_id: uuid.UUID, current_user: User, db: Session) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")
    return vehicle


@router.get("/lookup/{meridiangrid_id}", response_model=MeridianGridLookupResponse)
def lookup_meridiangrid_id(meridiangrid_id: str, current_user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)) -> MeridianGridProvisioning:
    provisioning = (
        db.query(MeridianGridProvisioning)
        .filter(MeridianGridProvisioning.meridiangrid_id == meridiangrid_id.strip().upper())
        .first()
    )
    if provisioning is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no vehicle found for this MeridianGrid ID")
    if provisioning.is_claimed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this MeridianGrid ID is already registered to a vehicle")
    return provisioning


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


@router.get("/requests/mine", response_model=list[VehicleRequestRead])
def list_my_vehicle_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[VehicleRequest]:
    return (
        db.query(VehicleRequest)
        .filter(VehicleRequest.user_id == current_user.id)
        .order_by(VehicleRequest.created_at.desc())
        .all()
    )


@router.get("/requests/track/{ticket_code}", response_model=VehicleRequestRead)
def track_vehicle_request(ticket_code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> VehicleRequest:
    req = (
        db.query(VehicleRequest)
        .filter(VehicleRequest.ticket_code == ticket_code.strip().upper(), VehicleRequest.user_id == current_user.id)
        .first()
    )
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no request found for this ticket ID")
    return req


@router.post("/requests/add", response_model=VehicleRequestRead, status_code=status.HTTP_201_CREATED)
def request_add_vehicle(payload: VehicleAddRequestCreate, current_user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)) -> VehicleRequest:
    meridiangrid_id = payload.meridiangrid_id.strip().upper()
    provisioning = (
        db.query(MeridianGridProvisioning)
        .filter(MeridianGridProvisioning.meridiangrid_id == meridiangrid_id)
        .first()
    )
    if provisioning is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no vehicle found for this MeridianGrid ID")
    if provisioning.is_claimed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this MeridianGrid ID is already registered to a vehicle")

    if not is_vellore_plate(payload.number_plate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="number plate must be a Vellore-registered plate (TN-23 series)",
        )

    existing = (
        db.query(VehicleRequest)
        .filter(
            VehicleRequest.meridiangrid_id == meridiangrid_id,
            VehicleRequest.request_type == "add",
            VehicleRequest.status == "pending",
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a pending add request already exists for this MeridianGrid ID")

    req = VehicleRequest(
        ticket_code=generate_ticket_code(),
        user_id=current_user.id,
        request_type="add",
        meridiangrid_id=meridiangrid_id,
        number_plate=normalize_plate(payload.number_plate),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.post("/requests/delete", response_model=VehicleRequestRead, status_code=status.HTTP_201_CREATED)
def request_delete_vehicle(payload: VehicleDeleteRequestCreate, current_user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)) -> VehicleRequest:
    vehicle = _get_owned_vehicle(payload.vehicle_id, current_user, db)

    if payload.reason_code not in DELETE_REASON_CODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unrecognized reason_code")
    if payload.reason_code == "other" and not (payload.reason_detail and payload.reason_detail.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reason_detail is required when reason_code is 'other'")

    existing = (
        db.query(VehicleRequest)
        .filter(
            VehicleRequest.vehicle_id == vehicle.id,
            VehicleRequest.request_type == "delete",
            VehicleRequest.status == "pending",
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a pending delete request already exists for this vehicle")

    req = VehicleRequest(
        ticket_code=generate_ticket_code(),
        user_id=current_user.id,
        request_type="delete",
        vehicle_id=vehicle.id,
        reason_code=payload.reason_code,
        reason_detail=payload.reason_detail,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
