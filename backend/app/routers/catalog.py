from dataclasses import asdict

from fastapi import APIRouter

from app.vehicle_catalog import VEHICLE_CATALOG

router = APIRouter(prefix="/vehicle-catalog", tags=["vehicle-catalog"])


@router.get("")
def list_catalog() -> list[dict]:
    return [asdict(entry) for entry in VEHICLE_CATALOG]
