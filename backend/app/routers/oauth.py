"""Real Google Sign-In: server-side ID-token verification against Google's
public keys.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import GoogleSignInRequest, TokenResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _find_or_create_oauth_user(db: Session, oauth_subject: str, email: str, name: str, provider: str) -> User:
    user = db.query(User).filter(User.oauth_subject == oauth_subject).first()
    if user is not None:
        return user

    existing_email_user = db.query(User).filter(User.email == email).first()
    if existing_email_user is not None:
        # Same person previously registered with password auth - link the
        # OAuth identity to that existing account rather than erroring.
        existing_email_user.oauth_subject = oauth_subject
        existing_email_user.auth_provider = provider
        db.commit()
        db.refresh(existing_email_user)
        return existing_email_user

    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(32)),  # unusable placeholder - login is OAuth-only
        persona="individual_driver",
        dpdp_consent_flag=True,
        auth_provider=provider,
        oauth_subject=oauth_subject,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/google", response_model=TokenResponse)
def google_sign_in(payload: GoogleSignInRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google Sign-In is not configured on this server yet - set GOOGLE_OAUTH_CLIENT_ID",
        )
    try:
        claims = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), settings.google_oauth_client_id,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Google ID token")

    user = _find_or_create_oauth_user(
        db, oauth_subject=claims["sub"], email=claims["email"],
        name=claims.get("name", claims["email"]), provider="google",
    )
    return TokenResponse(access_token=create_access_token(user.id, user.persona))
