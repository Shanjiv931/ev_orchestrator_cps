"""Seeds exactly one admin account on first boot, so there is always a way
to bootstrap the admin-approval workflow (Section: only an existing admin
can approve another admin - nobody can self-register as city_admin)."""
import logging

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.models import User

log = logging.getLogger("seed")


def seed_admin_if_missing(db: Session) -> None:
    existing_admin = db.query(User).filter(User.persona == "city_admin").first()
    if existing_admin is not None:
        return

    admin = User(
        name=settings.admin_seed_name,
        email=settings.admin_seed_email,
        hashed_password=hash_password(settings.admin_seed_password),
        persona="city_admin",
        dpdp_consent_flag=True,
        auth_provider="password",
        email_verified=True,  # bootstrapped by the operator, not self-registered
    )
    db.add(admin)
    db.commit()
    log.warning(
        "Seeded first admin account: %s / %s - change this password immediately "
        "(set ADMIN_SEED_EMAIL/ADMIN_SEED_PASSWORD before first boot to avoid this default).",
        settings.admin_seed_email, settings.admin_seed_password,
    )
