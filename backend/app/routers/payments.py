import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ChargingSession, User
from ml.upi_simulator import confirm_payment, get_payment, initiate_payment

router = APIRouter(prefix="/payments", tags=["payments"])


def _get_owned_session(session_id: uuid.UUID, current_user: User, db: Session) -> ChargingSession:
    session = db.get(ChargingSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session


@router.post("/sessions/{session_id}/initiate")
def initiate_session_payment(session_id: uuid.UUID, current_user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)) -> dict:
    session = _get_owned_session(session_id, current_user, db)
    payment = initiate_payment(session_id=str(session.id), amount_rupees=session.cost)
    return {
        "reference": payment.reference,
        "amount_rupees": payment.amount_rupees,
        "qr_payload": payment.qr_payload,
        "status": payment.status,
        "note": "SIMULATED PAYMENT - no real money moves, no real UPI PSP is contacted",
    }


@router.post("/{reference}/confirm")
def confirm_simulated_payment(reference: str, current_user: User = Depends(get_current_user)) -> dict:
    try:
        payment = confirm_payment(reference)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown payment reference")
    return {"reference": payment.reference, "status": payment.status}


@router.get("/{reference}")
def get_simulated_payment(reference: str, current_user: User = Depends(get_current_user)) -> dict:
    payment = get_payment(reference)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown payment reference")
    return {"reference": payment.reference, "status": payment.status, "amount_rupees": payment.amount_rupees}
