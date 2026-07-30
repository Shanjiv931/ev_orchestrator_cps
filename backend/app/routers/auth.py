from datetime import datetime, timezone

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
from app.database import get_db
from app.email_service import send_otp_email
from app.models import User
from app.pending_registration import (
    create_pending_registration,
    delete_pending_registration,
    get_pending_registration,
    update_pending_registration_otp,
)
from app.schemas import (
    LocationUpdate,
    LoginRequest,
    OtpVerifyRequest,
    PendingRegistrationResponse,
    ResendOtpRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Resending immediately on every request would let someone hammer a stranger's
# inbox for free via Resend - a minimal cooldown, not full rate limiting.
_OTP_RESEND_COOLDOWN_SECONDS = 30


@router.post("/register", response_model=PendingRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> PendingRegistrationResponse:
    if payload.persona == "city_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="city_admin can't be self-registered - sign up as individual_driver, "
                   "then request admin approval via POST /admin/requests",
        )
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    # No User row yet - per the project owner's requirement, registration is
    # only ever persisted once the OTP is verified (see verify_otp below).
    # Everything needed to create that row lives in Redis until then.
    otp_code = generate_otp_code()
    pending_id = create_pending_registration(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        persona=payload.persona,
        dpdp_consent_flag=payload.dpdp_consent_flag,
        otp_code_hash=hash_otp_code(otp_code),
        otp_expires_at=otp_expiry(),
    )
    send_otp_email(payload.email, otp_code)
    return PendingRegistrationResponse(pending_registration_id=pending_id, email=payload.email)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: OtpVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    pending = get_pending_registration(payload.pending_registration_id)
    expired_or_wrong = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="incorrect or expired code")
    if pending is None:
        raise expired_or_wrong
    otp_expires_at = datetime.fromisoformat(pending["otp_expires_at"])
    if otp_expires_at < datetime.now(timezone.utc) or not verify_otp_code(payload.otp_code, pending["otp_code_hash"]):
        raise expired_or_wrong

    user = User(
        name=pending["name"],
        email=pending["email"],
        hashed_password=pending["hashed_password"],
        persona=pending["persona"],
        dpdp_consent_flag=pending["dpdp_consent_flag"],
        email_verified=True,  # the OTP just confirmed this
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # someone else registered (and verified) the same email in the
        # window between this registration and this verification
        db.rollback()
        delete_pending_registration(payload.pending_registration_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    db.refresh(user)
    delete_pending_registration(payload.pending_registration_id)
    return TokenResponse(access_token=create_access_token(user.id, user.persona))


@router.post("/resend-otp", status_code=status.HTTP_204_NO_CONTENT)
def resend_otp(payload: ResendOtpRequest) -> None:
    pending = get_pending_registration(payload.pending_registration_id)
    if pending is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="registration expired - please register again")
    last_sent_at = datetime.fromisoformat(pending["last_sent_at"])
    seconds_since_last_send = (datetime.now(timezone.utc) - last_sent_at).total_seconds()
    if seconds_since_last_send < _OTP_RESEND_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"please wait {round(_OTP_RESEND_COOLDOWN_SECONDS - seconds_since_last_send)}s before requesting another code",
        )
    otp_code = generate_otp_code()
    update_pending_registration_otp(
        payload.pending_registration_id, otp_code_hash=hash_otp_code(otp_code), otp_expires_at=otp_expiry(),
    )
    send_otp_email(pending["email"], otp_code)


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
