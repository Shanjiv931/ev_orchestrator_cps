from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    generate_otp_code,
    get_current_user,
    get_current_user_allow_unverified,
    hash_otp_code,
    hash_password,
    otp_expiry,
    verify_otp_code,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.email_service import send_otp_email
from app.models import User
from app.schemas import LocationUpdate, LoginRequest, OtpVerifyRequest, TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

# Resending immediately on every request would let someone hammer a stranger's
# inbox for free via Resend - a minimal cooldown, not full rate limiting.
_OTP_RESEND_COOLDOWN_SECONDS = 30


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    if payload.persona == "city_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="city_admin can't be self-registered - sign up as individual_driver, "
                   "then request admin approval via POST /admin/requests",
        )
    otp_code = generate_otp_code()
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        persona=payload.persona,
        dpdp_consent_flag=payload.dpdp_consent_flag,
        email_verified=False,
        otp_code_hash=hash_otp_code(otp_code),
        otp_expires_at=otp_expiry(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    db.refresh(user)
    send_otp_email(user.email, otp_code)
    # Issued immediately so the frontend has an identity to call /auth/me and
    # /auth/verify-otp with - get_current_user (used by every other route)
    # rejects it until email_verified flips true, see app/auth.py.
    return TokenResponse(access_token=create_access_token(user.id, user.persona))


@router.post("/verify-otp", response_model=UserRead)
def verify_otp(payload: OtpVerifyRequest, current_user: User = Depends(get_current_user_allow_unverified),
               db: Session = Depends(get_db)) -> User:
    if current_user.email_verified:
        return current_user
    if (
        current_user.otp_code_hash is None
        or current_user.otp_expires_at is None
        or current_user.otp_expires_at < datetime.now(timezone.utc)
        or not verify_otp_code(payload.otp_code, current_user.otp_code_hash)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="incorrect or expired code")
    current_user.email_verified = True
    current_user.otp_code_hash = None
    current_user.otp_expires_at = None
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/resend-otp", status_code=status.HTTP_204_NO_CONTENT)
def resend_otp(current_user: User = Depends(get_current_user_allow_unverified), db: Session = Depends(get_db)) -> None:
    if current_user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="already verified")
    if current_user.otp_expires_at is not None:
        sent_at = current_user.otp_expires_at - timedelta(minutes=settings.otp_expire_minutes)
        seconds_since_last_send = (datetime.now(timezone.utc) - sent_at).total_seconds()
        if seconds_since_last_send < _OTP_RESEND_COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"please wait {round(_OTP_RESEND_COOLDOWN_SECONDS - seconds_since_last_send)}s before requesting another code",
            )
    otp_code = generate_otp_code()
    current_user.otp_code_hash = hash_otp_code(otp_code)
    current_user.otp_expires_at = otp_expiry()
    db.commit()
    send_otp_email(current_user.email, otp_code)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise unauthorized
    return TokenResponse(access_token=create_access_token(user.id, user.persona))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user_allow_unverified)) -> User:
    return current_user


@router.patch("/me/location", response_model=UserRead)
def update_my_location(payload: LocationUpdate, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> User:
    current_user.location_state = payload.location_state
    current_user.location_city = payload.location_city
    current_user.lat = payload.lat
    current_user.lon = payload.lon
    db.commit()
    db.refresh(current_user)
    return current_user
