"""Holds a not-yet-verified registration's details in Redis, not Postgres -
per the project owner's explicit requirement that a registration is only
ever persisted (a real row in `users`) once its OTP is verified. Redis's TTL
expiry also means an abandoned registration cleans itself up automatically,
with no scheduled job needed.
"""
import json
import uuid
from datetime import date, datetime, timezone

from app.config import settings
from app.redis_client import redis_client

_KEY_PREFIX = "pending_registration:"
# Generous relative to otp_expire_minutes so a resend right at the OTP's
# logical expiry still has a live Redis key to refresh - the logical
# expiry (checked explicitly in auth.py) is what actually gates a verify
# attempt, not this TTL, which exists only as a garbage-collection backstop.
_KEY_TTL_SECONDS = settings.otp_expire_minutes * 60 + 600


def create_pending_registration(
    *, name: str, email: str, hashed_password: str, persona: str, dpdp_consent_flag: bool,
    date_of_birth: date, phone_number: str, license_number: str, license_expiry: date, profession: str,
    otp_code_hash: str, otp_expires_at: datetime,
) -> str:
    pending_id = str(uuid.uuid4())
    _store(pending_id, {
        "name": name,
        "email": email,
        "hashed_password": hashed_password,
        "persona": persona,
        "dpdp_consent_flag": dpdp_consent_flag,
        "date_of_birth": date_of_birth.isoformat(),
        "phone_number": phone_number,
        "license_number": license_number,
        "license_expiry": license_expiry.isoformat(),
        "profession": profession,
        "otp_code_hash": otp_code_hash,
        "otp_expires_at": otp_expires_at.isoformat(),
        "last_sent_at": datetime.now(timezone.utc).isoformat(),
    })
    return pending_id


def get_pending_registration(pending_id: str) -> dict | None:
    raw = redis_client.get(_KEY_PREFIX + pending_id)
    if raw is None:
        return None
    return json.loads(raw)


def update_pending_registration_otp(pending_id: str, *, otp_code_hash: str, otp_expires_at: datetime) -> None:
    data = get_pending_registration(pending_id)
    if data is None:
        return
    data["otp_code_hash"] = otp_code_hash
    data["otp_expires_at"] = otp_expires_at.isoformat()
    data["last_sent_at"] = datetime.now(timezone.utc).isoformat()
    _store(pending_id, data)


def delete_pending_registration(pending_id: str) -> None:
    redis_client.delete(_KEY_PREFIX + pending_id)


def _store(pending_id: str, data: dict) -> None:
    redis_client.setex(_KEY_PREFIX + pending_id, _KEY_TTL_SECONDS, json.dumps(data))
