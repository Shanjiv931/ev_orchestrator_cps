import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_admin, get_current_user
from app.database import get_db
from app.models import AdminRequest, Charger, ChargingSession, MeridianGridProvisioning, Station, User, Vehicle, VehicleRequest
from app.routers.vehicle_link import _simulated_telemetry
from app.schemas import (
    AdminRequestRead,
    CrossDistrictChargingRead,
    DemandRetrainRead,
    UserRead,
    VelloreFleetVehicleRead,
    VehicleRequestRead,
    VehicleRequestReview,
)
from app.services.demand_retrain_job import force_retrain
from app.vellore import is_vellore_plate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/requests", response_model=AdminRequestRead, status_code=status.HTTP_201_CREATED)
def request_admin_access(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AdminRequest:
    if current_user.persona == "city_admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="already an admin")
    existing = (
        db.query(AdminRequest)
        .filter(AdminRequest.user_id == current_user.id, AdminRequest.status == "pending")
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a pending request already exists")
    req = AdminRequest(user_id=current_user.id)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/requests", response_model=list[AdminRequestRead])
def list_admin_requests(status_filter: str = "pending", current_admin: User = Depends(get_current_admin),
                         db: Session = Depends(get_db)) -> list[AdminRequest]:
    query = db.query(AdminRequest)
    if status_filter != "all":
        query = query.filter(AdminRequest.status == status_filter)
    return query.order_by(AdminRequest.requested_at.desc()).all()


def _get_pending_request(request_id: uuid.UUID, db: Session) -> AdminRequest:
    req = db.get(AdminRequest, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="admin request not found")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"request already {req.status}")
    return req


@router.post("/requests/{request_id}/approve", response_model=AdminRequestRead)
def approve_admin_request(request_id: uuid.UUID, current_admin: User = Depends(get_current_admin),
                           db: Session = Depends(get_db)) -> AdminRequest:
    req = _get_pending_request(request_id, db)
    target_user = db.get(User, req.user_id)
    target_user.persona = "city_admin"
    req.status = "approved"
    req.reviewed_by = current_admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.post("/requests/{request_id}/reject", response_model=AdminRequestRead)
def reject_admin_request(request_id: uuid.UUID, current_admin: User = Depends(get_current_admin),
                          db: Session = Depends(get_db)) -> AdminRequest:
    req = _get_pending_request(request_id, db)
    req.status = "rejected"
    req.reviewed_by = current_admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.get("/users", response_model=list[UserRead])
def list_all_users(current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.name).all()


@router.get("/vehicle-requests", response_model=list[VehicleRequestRead])
def list_vehicle_requests(status_filter: str = "pending", current_admin: User = Depends(get_current_admin),
                           db: Session = Depends(get_db)) -> list[VehicleRequest]:
    query = db.query(VehicleRequest)
    if status_filter != "all":
        query = query.filter(VehicleRequest.status == status_filter)
    return query.order_by(VehicleRequest.created_at.desc()).all()


def _get_pending_vehicle_request(request_id: uuid.UUID, db: Session) -> VehicleRequest:
    req = db.get(VehicleRequest, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle request not found")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"request already {req.status}")
    return req


@router.post("/vehicle-requests/{request_id}/approve", response_model=VehicleRequestRead)
def approve_vehicle_request(request_id: uuid.UUID, payload: VehicleRequestReview = VehicleRequestReview(),
                             current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> VehicleRequest:
    req = _get_pending_vehicle_request(request_id, db)

    if req.request_type == "add":
        provisioning = (
            db.query(MeridianGridProvisioning)
            .filter(MeridianGridProvisioning.meridiangrid_id == req.meridiangrid_id)
            .first()
        )
        if provisioning is None or provisioning.is_claimed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MeridianGrid ID is no longer available")
        vehicle = Vehicle(
            user_id=req.user_id,
            vehicle_class=provisioning.vehicle_class,
            connector_type=provisioning.connector_type,
            battery_chemistry=provisioning.battery_chemistry,
            is_pluggable=provisioning.is_pluggable,
            brand=provisioning.brand,
            vehicle_model=provisioning.vehicle_model,
            battery_capacity_kwh=provisioning.battery_capacity_kwh,
            color_hex=provisioning.color_hex,
            number_plate=req.number_plate,
        )
        provisioning.is_claimed = True
        db.add(vehicle)
    else:
        vehicle = db.get(Vehicle, req.vehicle_id)
        if vehicle is not None:
            # this same request row FKs to the vehicle being deleted - null
            # it out first or the DELETE violates that foreign key
            req.vehicle_id = None
            db.delete(vehicle)

    req.status = "approved"
    req.admin_notes = payload.admin_notes
    req.reviewed_by = current_admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.post("/vehicle-requests/{request_id}/reject", response_model=VehicleRequestRead)
def reject_vehicle_request(request_id: uuid.UUID, payload: VehicleRequestReview = VehicleRequestReview(),
                            current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> VehicleRequest:
    req = _get_pending_vehicle_request(request_id, db)
    req.status = "rejected"
    req.admin_notes = payload.admin_notes
    req.reviewed_by = current_admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.get("/vellore-fleet", response_model=list[VelloreFleetVehicleRead])
def list_vellore_fleet(current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[VelloreFleetVehicleRead]:
    """Every vehicle registered under the Vellore admin's district - plate,
    owner identity/profession/license, and live battery status, so the
    admin never has to cross-reference users and vehicles by hand. Vehicles
    with no plate on file (rows that predate app/vellore.py's Vellore-only
    validation) aren't verifiably Vellore-registered, so they're excluded
    rather than guessed at."""
    rows = db.query(Vehicle, User).join(User, Vehicle.user_id == User.id).all()
    fleet: list[VelloreFleetVehicleRead] = []
    for vehicle, owner in rows:
        if not vehicle.number_plate or not is_vellore_plate(vehicle.number_plate):
            continue
        telemetry = _simulated_telemetry(vehicle) if vehicle.is_paired else None
        fleet.append(VelloreFleetVehicleRead(
            vehicle_id=vehicle.id,
            number_plate=vehicle.number_plate,
            vehicle_class=vehicle.vehicle_class,
            brand=vehicle.brand,
            vehicle_model=vehicle.vehicle_model,
            connector_type=vehicle.connector_type,
            owner_name=owner.name,
            owner_profession=owner.profession,
            owner_license_number=owner.license_number,
            owner_license_expiry=owner.license_expiry,
            owner_phone_number=owner.phone_number,
            is_paired=vehicle.is_paired,
            battery_pct=telemetry.battery_pct if telemetry else None,
            is_charging=telemetry.is_charging if telemetry else None,
        ))
    return fleet


@router.get("/cross-district-charging", response_model=list[CrossDistrictChargingRead])
def list_cross_district_charging(current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[CrossDistrictChargingRead]:
    """Vehicles plated outside Vellore that are mid-session on Vellore
    infrastructure right now - the Vellore admin's window into vehicles
    from other districts using local chargers. Always empty today:
    registration only accepts Vellore plates (app/vellore.py), so no
    non-Vellore vehicle can exist yet. The query itself is real and will
    start returning rows the moment that restriction is ever relaxed for
    another district."""
    rows = (
        db.query(ChargingSession, Vehicle, User, Station)
        .join(Vehicle, ChargingSession.vehicle_id == Vehicle.id)
        .join(User, ChargingSession.user_id == User.id)
        .join(Charger, ChargingSession.charger_id == Charger.id)
        .join(Station, Charger.station_id == Station.id)
        .filter(ChargingSession.end_time.is_(None), Station.city == "Vellore")
        .all()
    )
    return [
        CrossDistrictChargingRead(
            vehicle_id=vehicle.id,
            number_plate=vehicle.number_plate,
            owner_name=owner.name,
            station_id=station.id,
            station_name=station.station_type,
            session_id=session.id,
            session_start_time=session.start_time,
        )
        for session, vehicle, owner, station in rows
        if not (vehicle.number_plate and is_vellore_plate(vehicle.number_plate))
    ]


@router.post("/retrain-demand-model", response_model=DemandRetrainRead)
def retrain_demand_model(current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> DemandRetrainRead:
    """Point 13: forces an immediate retrain against real accumulated
    ChargingBehaviorLog rows blended behind the synthetic baseline (see
    app/services/demand_retrain_job.py) - what a daily cron would trigger
    in production; exposed here so the Vellore admin can also trigger it
    on demand and see exactly how much real data went into it."""
    result = force_retrain(db)
    return DemandRetrainRead(
        mae=result["mae"], rmse=result["rmse"],
        real_data_rows=result["real_data_rows"], synthetic_rows=result["synthetic_rows"],
    )
