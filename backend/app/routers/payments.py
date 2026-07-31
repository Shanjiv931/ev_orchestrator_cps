import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Charger, ChargingSession, Station, User
from app.schemas import PaySessionRequest, SessionPaymentRead

router = APIRouter(prefix="/payments", tags=["payments"])

# No simulated UPI/QR flow - a charging session is paid for in person at the
# station, and this is just which method the user used there.
PAYMENT_METHODS = ["upi", "card", "cash"]


def _get_owned_session(session_id: uuid.UUID, current_user: User, db: Session) -> ChargingSession:
    session = db.get(ChargingSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session


def _to_payment_read(session: ChargingSession, db: Session) -> SessionPaymentRead:
    station = None
    if session.charger_id is not None:
        charger = db.get(Charger, session.charger_id)
        if charger is not None:
            station = db.get(Station, charger.station_id)
    return SessionPaymentRead(
        session_id=session.id,
        station_id=station.id if station else None,
        station_name=station.station_type if station else None,
        cost=session.cost,
        payment_status=session.payment_status,
        payment_method=session.payment_method,
        paid_at=session.paid_at,
    )


@router.get("/sessions/{session_id}", response_model=SessionPaymentRead)
def get_session_payment(session_id: uuid.UUID, current_user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)) -> SessionPaymentRead:
    session = _get_owned_session(session_id, current_user, db)
    return _to_payment_read(session, db)


@router.post("/sessions/{session_id}/pay", response_model=SessionPaymentRead)
def pay_for_session(session_id: uuid.UUID, payload: PaySessionRequest, current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> SessionPaymentRead:
    session = _get_owned_session(session_id, current_user, db)
    if session.payment_status == "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session already paid")
    if payload.method not in PAYMENT_METHODS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unrecognized payment method")

    session.payment_status = "paid"
    session.payment_method = payload.method
    session.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return _to_payment_read(session, db)
