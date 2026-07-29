import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CarbonLedgerEntry, ChargingSession, User
from app.schemas import CarbonLedgerRead

router = APIRouter(prefix="/carbon-ledger", tags=["carbon-ledger"])


@router.get("/sessions/{session_id}", response_model=list[CarbonLedgerRead])
def list_entries_for_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[CarbonLedgerEntry]:
    session = db.get(ChargingSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return db.query(CarbonLedgerEntry).filter(CarbonLedgerEntry.session_id == session_id).all()


@router.get("/me/summary")
def my_carbon_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    total_kg = (
        db.query(CarbonLedgerEntry)
        .join(ChargingSession, CarbonLedgerEntry.session_id == ChargingSession.id)
        .filter(ChargingSession.user_id == current_user.id)
        .with_entities(CarbonLedgerEntry.co2_avoided_kg)
        .all()
    )
    return {"total_co2_avoided_kg": round(sum(row[0] for row in total_kg), 3), "session_count": len(total_kg)}
