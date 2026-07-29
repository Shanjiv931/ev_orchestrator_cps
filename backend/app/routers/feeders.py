import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GridFeeder
from app.schemas import GridFeederCreate, GridFeederRead, GridFeederUpdate

router = APIRouter(prefix="/feeders", tags=["feeders"])


@router.post("", response_model=GridFeederRead, status_code=status.HTTP_201_CREATED)
def create_feeder(payload: GridFeederCreate, db: Session = Depends(get_db)) -> GridFeeder:
    feeder = GridFeeder(**payload.model_dump())
    db.add(feeder)
    db.commit()
    db.refresh(feeder)
    return feeder


@router.get("", response_model=list[GridFeederRead])
def list_feeders(is_rural_minigrid: bool | None = None, db: Session = Depends(get_db)) -> list[GridFeeder]:
    query = db.query(GridFeeder)
    if is_rural_minigrid is not None:
        query = query.filter(GridFeeder.is_rural_minigrid == is_rural_minigrid)
    return query.all()


@router.get("/{feeder_id}", response_model=GridFeederRead)
def get_feeder(feeder_id: uuid.UUID, db: Session = Depends(get_db)) -> GridFeeder:
    feeder = db.get(GridFeeder, feeder_id)
    if feeder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feeder not found")
    return feeder


@router.patch("/{feeder_id}", response_model=GridFeederRead)
def update_feeder(feeder_id: uuid.UUID, payload: GridFeederUpdate, db: Session = Depends(get_db)) -> GridFeeder:
    feeder = db.get(GridFeeder, feeder_id)
    if feeder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feeder not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(feeder, field, value)
    db.commit()
    db.refresh(feeder)
    return feeder
