import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ChargingSession, HomeCharger, User, Vehicle
from app.schemas import HomeChargerCreate, HomeChargerRead, SessionRead, StartHomeSessionRequest

router = APIRouter(prefix="/home-chargers", tags=["home-charging"])


def _get_owned_home_charger(home_charger_id: uuid.UUID, current_user: User, db: Session) -> HomeCharger:
    charger = db.get(HomeCharger, home_charger_id)
    if charger is None or charger.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="home charger not found")
    return charger


@router.post("", response_model=HomeChargerRead, status_code=status.HTTP_201_CREATED)
def register_home_charger(payload: HomeChargerCreate, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> HomeCharger:
    lat = payload.lat if payload.lat is not None else current_user.lat
    lon = payload.lon if payload.lon is not None else current_user.lon
    if lat is None or lon is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no location on file - set your home location or pass lat/lon explicitly",
        )
    charger = HomeCharger(user_id=current_user.id, label=payload.label, power_kw=payload.power_kw, lat=lat, lon=lon)
    db.add(charger)
    db.commit()
    db.refresh(charger)
    return charger


@router.get("", response_model=list[HomeChargerRead])
def list_my_home_chargers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[HomeCharger]:
    return db.query(HomeCharger).filter(HomeCharger.user_id == current_user.id).all()


@router.delete("/{home_charger_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_home_charger(home_charger_id: uuid.UUID, current_user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)) -> None:
    charger = _get_owned_home_charger(home_charger_id, current_user, db)
    db.delete(charger)
    db.commit()


@router.post("/start-session", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def start_home_session(payload: StartHomeSessionRequest, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> ChargingSession:
    """No port assignment or availability check needed - a home charger is
    exclusive to its owner, unlike a public station's shared chargers (see
    app/routers/sessions.py's start-at-station)."""
    home_charger = _get_owned_home_charger(payload.home_charger_id, current_user, db)
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if vehicle is None or vehicle.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle not found")

    existing = (
        db.query(ChargingSession)
        .filter(ChargingSession.home_charger_id == home_charger.id, ChargingSession.end_time.is_(None))
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this home charger already has a session in progress")

    session = ChargingSession(user_id=current_user.id, vehicle_id=payload.vehicle_id, home_charger_id=home_charger.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
