import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_admin, get_current_user
from app.database import get_db
from app.models import AdminRequest, User
from app.schemas import AdminRequestRead, UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/requests", response_model=AdminRequestRead, status_code=status.HTTP_201_CREATED)
def request_admin_access(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AdminRequest:
    if current_user.persona == "city_admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="already an admin")
    existing = (
        db.query(AdminRequest)
        .filter(AdminRequest.user_id == current_user.id, AdminRequest.status == "pending")
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a pending request already exists")
    req = AdminRequest(user_id=current_user.id)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/requests", response_model=list[AdminRequestRead])
def list_admin_requests(status_filter: str = "pending", current_admin: User = Depends(get_current_admin),
                         db: Session = Depends(get_db)) -> list[AdminRequest]:
    query = db.query(AdminRequest)
    if status_filter != "all":
        query = query.filter(AdminRequest.status == status_filter)
    return query.order_by(AdminRequest.requested_at.desc()).all()


def _get_pending_request(request_id: uuid.UUID, db: Session) -> AdminRequest:
    req = db.get(AdminRequest, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="admin request not found")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"request already {req.status}")
    return req


@router.post("/requests/{request_id}/approve", response_model=AdminRequestRead)
def approve_admin_request(request_id: uuid.UUID, current_admin: User = Depends(get_current_admin),
                           db: Session = Depends(get_db)) -> AdminRequest:
    req = _get_pending_request(request_id, db)
    target_user = db.get(User, req.user_id)
    target_user.persona = "city_admin"
    req.status = "approved"
    req.reviewed_by = current_admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.post("/requests/{request_id}/reject", response_model=AdminRequestRead)
def reject_admin_request(request_id: uuid.UUID, current_admin: User = Depends(get_current_admin),
                          db: Session = Depends(get_db)) -> AdminRequest:
    req = _get_pending_request(request_id, db)
    req.status = "rejected"
    req.reviewed_by = current_admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.get("/users", response_model=list[UserRead])
def list_all_users(current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.name).all()
