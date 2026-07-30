"""DPDP-aligned data retention job (Section 4.7).

Every user carries a `consent_expiry`; this job is the actual enforcement
of that limit - it finds users whose consent has expired and erases their
personal data, rather than leaving the column as documentation of an
intent nobody acts on. Deletion is a real cascading delete across every
table that references the user (directly or via their vehicles/sessions),
run in dependency order so foreign key constraints are never violated.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BatteryHealth, CarbonLedgerEntry, ChargingSession, Telemetry, User, Vehicle


def find_expired_users(db: Session, now: datetime | None = None) -> list[User]:
    now = now or datetime.now(timezone.utc)
    return list(db.scalars(
        select(User).where(User.consent_expiry.is_not(None)).where(User.consent_expiry < now)
    ).all())


def erase_user(db: Session, user: User) -> None:
    """Cascading erasure in FK-safe order: telemetry and carbon-ledger
    entries (via sessions), sessions, battery-health records (via
    vehicles), vehicles, then the user row itself."""
    vehicle_ids = list(db.scalars(select(Vehicle.id).where(Vehicle.user_id == user.id)).all())
    session_ids = list(db.scalars(select(ChargingSession.id).where(ChargingSession.user_id == user.id)).all())

    if session_ids:
        db.query(Telemetry).filter(Telemetry.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(CarbonLedgerEntry).filter(CarbonLedgerEntry.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(ChargingSession).filter(ChargingSession.id.in_(session_ids)).delete(synchronize_session=False)

    if vehicle_ids:
        db.query(BatteryHealth).filter(BatteryHealth.vehicle_id.in_(vehicle_ids)).delete(synchronize_session=False)
        db.query(Vehicle).filter(Vehicle.id.in_(vehicle_ids)).delete(synchronize_session=False)

    db.delete(user)


def run_retention_sweep(db: Session, now: datetime | None = None) -> int:
    """Returns the number of users erased."""
    expired_users = find_expired_users(db, now)
    for user in expired_users:
        erase_user(db, user)
    db.commit()
    return len(expired_users)


if __name__ == "__main__":
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        erased_count = run_retention_sweep(session)
        print(f"DPDP retention sweep: erased {erased_count} user(s) past consent expiry")
    finally:
        session.close()
