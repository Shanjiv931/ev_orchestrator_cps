from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import LocationUpdate, LoginRequest, TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    if payload.persona == "city_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="city_admin can't be self-registered - sign up as individual_driver, "
                   "then request admin approval via POST /admin/requests",
        )
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        persona=payload.persona,
        dpdp_consent_flag=payload.dpdp_consent_flag,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id, user.persona))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise unauthorized
    return TokenResponse(access_token=create_access_token(user.id, user.persona))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
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
