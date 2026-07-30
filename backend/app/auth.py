"""Password hashing and JWT issuing/verification for the auth extension to
Section 8's USERS entity (see models/entities.py for why it exists)."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(code: str) -> str:
    return pwd_context.hash(code)


def verify_otp_code(plain_code: str, hashed_code: str) -> bool:
    return pwd_context.verify(plain_code, hashed_code)


def otp_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)


def create_access_token(user_id: uuid.UUID, persona: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "persona": persona, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_current_user(token: str | None, db: Session) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing credentials")
    if token is None:
        raise unauthorized
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def get_current_user_allow_unverified(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Identity only, no email-verification check. Only for the handful of
    endpoints an unverified account must still reach: /auth/me (so the
    frontend can even learn it's unverified) and the OTP verify/resend
    endpoints themselves. Everything else uses get_current_user below."""
    return _decode_current_user(token, db)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user = _decode_current_user(token, db)
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="email not verified - check your inbox for the confirmation code",
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """City-admin-only dependency. Registration can never set this persona
    directly - see app/routers/admin.py's approval workflow."""
    if current_user.persona != "city_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin access required")
    return current_user
