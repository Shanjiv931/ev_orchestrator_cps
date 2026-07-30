"""Simulated vehicle-to-app pairing and live telemetry.

No real manufacturer telematics API is integrated here (Tata iRA, MG
iSMART, Ather app, etc. all require commercial partnerships this project
does not have) - consistent with the build's own "no physical hardware,
simulate every output" rule. This gives the same UX shape a real
integration would (a pairing code, a "paired" state, a live telemetry
feed) with data generated deterministically per vehicle rather than
pulled from a car. Every response is explicitly flagged `is_simulated`.
"""
import hashlib
import math
import secrets
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Vehicle
from app.schemas import VehicleLiveTelemetry, VehiclePairingResponse

router = APIRouter(prefix="/vehicles", tags=["vehicle-link"])

CONSUMPTION_KWH_PER_KM = {"2W": 0.03, "3W": 0.06, "4W": 0.15}


def _get_owned_vehicle(vehicle_id: uuid.UUID, current_user: User, db: Session) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")
    return vehicle


@router.post("/{vehicle_id}/pair", response_model=VehiclePairingResponse)
def start_pairing(vehicle_id: uuid.UUID, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> VehiclePairingResponse:
    vehicle = _get_owned_vehicle(vehicle_id, current_user, db)
    code = secrets.token_hex(3).upper()  # 6 hex chars, e.g. "A93F2C" - shown as a fake in-car display code
    vehicle.pairing_code = code
    vehicle.is_paired = False
    db.commit()
    return VehiclePairingResponse(pairing_code=code, vehicle_id=vehicle.id)


@router.post("/{vehicle_id}/pair/confirm", response_model=VehiclePairingResponse)
def confirm_pairing(vehicle_id: uuid.UUID, code: str, current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> VehiclePairingResponse:
    vehicle = _get_owned_vehicle(vehicle_id, current_user, db)
    if not vehicle.pairing_code or code.upper() != vehicle.pairing_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="incorrect pairing code")
    vehicle.is_paired = True
    db.commit()
    return VehiclePairingResponse(pairing_code=vehicle.pairing_code, vehicle_id=vehicle.id)


def _simulated_telemetry(vehicle: Vehicle) -> VehicleLiveTelemetry:
    """Deterministic-but-live-looking values: a per-vehicle phase offset (from
    a hash of its id) plus the current time drives a slow charge/discharge
    cycle, so refreshing the page shows smoothly changing numbers instead of
    a static fixture, without needing any real hardware link."""
    seed = int(hashlib.sha256(str(vehicle.id).encode()).hexdigest(), 16)
    phase_offset = (seed % 1000) / 1000.0 * 2 * math.pi
    cycle_seconds = 3600.0  # one full charge/discharge cycle per simulated hour
    t = (time.time() / cycle_seconds * 2 * math.pi) + phase_offset
    battery_pct = 55.0 + 40.0 * math.sin(t)
    is_charging = math.cos(t) > 0

    capacity_kwh = vehicle.battery_capacity_kwh or {"2W": 3.5, "3W": 8.0, "4W": 40.0}[vehicle.vehicle_class]
    consumption = CONSUMPTION_KWH_PER_KM.get(vehicle.vehicle_class, 0.15)
    range_km = (battery_pct / 100.0) * capacity_kwh / consumption
    odometer_km = 1000.0 + (seed % 50000) / 10.0 + (time.time() % 86400) / 86400.0 * 5.0

    return VehicleLiveTelemetry(
        vehicle_id=vehicle.id,
        is_simulated=True,
        battery_pct=round(max(0.0, min(100.0, battery_pct)), 1),
        is_charging=is_charging,
        range_km=round(range_km, 1),
        odometer_km=round(odometer_km, 1),
        last_updated=datetime.now(timezone.utc),
    )


@router.get("/{vehicle_id}/live-telemetry", response_model=VehicleLiveTelemetry)
def get_live_telemetry(vehicle_id: uuid.UUID, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> VehicleLiveTelemetry:
    vehicle = _get_owned_vehicle(vehicle_id, current_user, db)
    if not vehicle.is_paired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="vehicle is not paired yet")
    return _simulated_telemetry(vehicle)
