"""Seeds a pool of unclaimed MeridianGrid IDs on first boot (only if the
provisioning table is empty) - standing in for a manufacturer's factory
system pre-registering chassis-linked IDs before a vehicle ever reaches a
customer. Each ID resolves to a full spec from app/vehicle_catalog.py, so
"entering the ID" (app/routers/vehicles.py's lookup/request-add endpoints)
is what replaces manual spec entry end to end.
"""
from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.models import MeridianGridProvisioning
from app.vehicle_catalog import VEHICLE_CATALOG

# Per catalog entry, not one ID per vehicle in existence - a healthy supply
# of demo IDs to hand out during testing/demoing the flow.
IDS_PER_CATALOG_ENTRY = 6
_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I - avoids visual ambiguity when read off a screen


def _group(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _generate_id() -> str:
    return f"MG-{_group(4)}-{_group(4)}"


def seed_provisioning_if_empty(db: Session) -> None:
    if db.query(MeridianGridProvisioning).count() > 0:
        return

    seen_ids: set[str] = set()
    for entry in VEHICLE_CATALOG:
        for _ in range(IDS_PER_CATALOG_ENTRY):
            code = _generate_id()
            while code in seen_ids:
                code = _generate_id()
            seen_ids.add(code)
            db.add(MeridianGridProvisioning(
                meridiangrid_id=code,
                vehicle_class=entry.vehicle_class,
                connector_type=entry.connector_type,
                battery_chemistry=entry.battery_chemistry,
                is_pluggable=entry.is_pluggable,
                brand=entry.brand,
                vehicle_model=entry.vehicle_model,
                battery_capacity_kwh=entry.battery_capacity_kwh,
                color_hex=entry.color_hex,
            ))

    db.commit()
