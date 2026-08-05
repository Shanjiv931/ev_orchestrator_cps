"""Generic admin database browser/editor - lists every table in the schema
(derived straight from Base.metadata, so it can never drift out of sync
with the actual models) and does controlled CRUD against any of them by
primary key. Deliberately not model-specific: this is a dev/ops tool for
the Vellore admin to inspect and correct data directly, not a
business-logic endpoint, so it bypasses the validation each resource's own
router enforces (e.g. Vellore-plate checks, OTP-gated user creation) on
purpose - that's the whole point of a raw database console, but it's also
why its write surface is deliberately narrower than a typical admin panel:

- No hard delete, anywhere. A raw DELETE with no trace is itself a
  compliance concern for PII/financial data (SOC2/ISO 27001, India's DPDP
  Act) even in cases where removing a row is legitimate - the safe pattern
  is a reviewable status change (e.g. a vehicle_request rejection, a
  charger set to "offline"), not silent, untracked erasure. If a table
  genuinely needs rows removed, that's a resource-specific decision
  belonging to that resource's own router, not this generic console.
- CREATE is blocked for transactional/log tables (sessions, telemetry,
  battery health readings, carbon ledger entries, behavior logs, model
  training runs) - manually inserting a row into a table the system itself
  is the only legitimate writer for breaks the audit trail those tables
  exist to provide. It stays open for reference/config tables (stations,
  chargers, vehicles, ...).
- UPDATE is restricted to a per-table allow-list of genuinely correctable
  fields (EDITABLE_FIELDS_BY_TABLE below) - e.g. a user's phone number or
  license number, a station's safety score, a charger's operational
  status - not structural/security-sensitive fields (password hashes,
  foreign keys, the trust-layer's last_verified_at, the fault-detection
  pipeline's maintenance_risk_score). A table with no entry in the
  allow-list has nothing editable through this console at all - safe by
  default, not permissive by default.
- Every create/update is written to AdminAuditLog (who, what table/row,
  before/after) - whatever this console CAN do, it leaves a trail for.
"""
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import Base, get_db
from app.models import AdminAuditLog, User

router = APIRouter(prefix="/admin/db", tags=["admin-database"])

# System-managed: the platform itself is the only legitimate writer, so a
# manually-inserted row here would be indistinguishable from (and corrupt)
# real audit/financial/training history.
TRANSACTIONAL_TABLES = {
    "sessions", "charging_behavior_log", "demand_model_training_runs",
    "telemetry", "battery_health", "carbon_ledger",
}

# Per-table allow-list of fields a database-console edit may touch. Deliberately
# excludes: auth/security fields (hashed_password, otp_*, oauth_subject,
# email_verified, persona - persona gates admin capability, so it's a
# privilege-escalation risk if raw-editable), foreign keys (reassigning a
# charger to a different station, a vehicle to a different user, etc. is a
# structural change, not a correction), and fields another automated system
# owns (Charger.maintenance_risk_score is written by the fault-detection
# pipeline - app/services/fault_consumer.py; Charger.last_verified_at is the
# trust-layer's own signal - app/routers/stations.py/stations_sim.py -
# manually setting either would falsify the exact signal the platform is
# built to keep honest; Charger.reserved_until/reserved_by_user_id and
# Station.queue_length are likewise system-managed).
EDITABLE_FIELDS_BY_TABLE: dict[str, set[str]] = {
    "users": {"name", "phone_number", "license_number", "license_expiry", "date_of_birth",
              "profession", "location_city", "location_state", "lat", "lon"},
    "vehicles": {"number_plate", "color_hex", "brand", "vehicle_model", "battery_capacity_kwh", "fleet_depot_id"},
    "stations": {"station_type", "safety_score", "has_solar", "city", "lat", "lon"},
    "chargers": {"status", "power_kw", "port_number"},
    "swap_slots": {"status", "batteries_available"},
    "grid_feeders": {"feeder_zone", "capacity_kw", "is_rural_minigrid"},
    "home_chargers": {"label", "power_kw", "lat", "lon"},
    "admin_requests": {"status", "reviewed_by", "reviewed_at"},
    "vehicle_requests": {"status", "admin_notes", "reviewed_by", "reviewed_at"},
    # meridiangrid_provisioning: no fields editable via this console - it's
    # treated as append-only factory-issued reference data (see its own
    # docstring in models/entities.py); corrections go through re-seeding.
}


def _get_table(table_name: str) -> Table:
    table = Base.metadata.tables.get(table_name)
    if table is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no table named '{table_name}'")
    return table


def _primary_key_column(table: Table):
    pk_columns = list(table.primary_key.columns)
    if len(pk_columns) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{table.name}' doesn't have a single-column primary key - not editable here",
        )
    return pk_columns[0]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict[str, Any]:
    return {key: _serialize_value(value) for key, value in row._mapping.items()}


def _coerce_value(column, value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    try:
        py_type = column.type.python_type
    except NotImplementedError:
        return value
    try:
        if py_type is uuid.UUID:
            return uuid.UUID(value)
        if py_type is datetime:
            return datetime.fromisoformat(value)
        if py_type is date:
            return date.fromisoformat(value)
        if py_type is bool:
            return value.lower() in ("true", "1", "yes")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{value}' is not a valid {py_type.__name__} for column '{column.name}'")
    return value


def _coerce_payload(table: Table, payload: dict[str, Any]) -> dict[str, Any]:
    unknown = set(payload) - set(table.columns.keys())
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown column(s) for '{table.name}': {sorted(unknown)}")
    return {key: _coerce_value(table.columns[key], value) for key, value in payload.items()}


def _record_audit(db: Session, admin: User, table_name: str, row_id: str, action: str,
                   before: dict | None, after: dict | None) -> None:
    db.add(AdminAuditLog(admin_user_id=admin.id, table_name=table_name, row_id=row_id,
                          action=action, before=before, after=after))


@router.get("/tables")
def list_tables(current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[dict]:
    tables = []
    for table in Base.metadata.sorted_tables:
        row_count = db.execute(select(func.count()).select_from(table)).scalar_one()
        columns = [
            {
                "name": col.name,
                "type": str(col.type),
                "nullable": col.nullable,
                "primary_key": col.primary_key,
                "foreign_key": next(iter(col.foreign_keys)).target_fullname if col.foreign_keys else None,
            }
            for col in table.columns
        ]
        tables.append({
            "name": table.name,
            "row_count": row_count,
            "columns": columns,
            "creatable": table.name not in TRANSACTIONAL_TABLES and table.name != "admin_audit_log",
            "editable_fields": sorted(EDITABLE_FIELDS_BY_TABLE.get(table.name, set())),
            "deletable": False,
        })
    return tables


@router.get("/tables/{table_name}/rows")
def list_rows(table_name: str, limit: int = 50, offset: int = 0,
              current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
    table = _get_table(table_name)
    limit = max(1, min(limit, 200))
    total = db.execute(select(func.count()).select_from(table)).scalar_one()
    pk_columns = list(table.primary_key.columns)
    query = select(table).limit(limit).offset(offset)
    if pk_columns:
        query = query.order_by(*pk_columns)
    rows = db.execute(query).all()
    return {"rows": [_serialize_row(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.post("/tables/{table_name}/rows", status_code=status.HTTP_201_CREATED)
def create_row(table_name: str, payload: dict[str, Any] = Body(...),
                current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
    table = _get_table(table_name)
    if table_name in TRANSACTIONAL_TABLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"'{table_name}' is system-written only - manually inserting a row would falsify its audit trail",
        )
    values = _coerce_payload(table, payload)
    try:
        result = db.execute(insert(table).values(**values).returning(*table.columns))
        row = _serialize_row(result.one())
        _record_audit(db, current_admin, table_name, str(row.get("id", "")), "create", before=None, after=row)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc.orig))
    return row


@router.patch("/tables/{table_name}/rows/{row_id}")
def update_row(table_name: str, row_id: str, payload: dict[str, Any] = Body(...),
               current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
    table = _get_table(table_name)
    pk_column = _primary_key_column(table)
    editable = EDITABLE_FIELDS_BY_TABLE.get(table_name, set())
    not_editable = set(payload) - editable
    if not_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"field(s) not editable via the database console for '{table_name}': {sorted(not_editable)}"
                   + (f" (editable: {sorted(editable)})" if editable else " (no fields on this table are editable here)"),
        )
    values = _coerce_payload(table, payload)
    coerced_id = _coerce_value(pk_column, row_id)

    before_row = db.execute(select(table).where(pk_column == coerced_id)).first()
    if before_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="row not found")
    before = _serialize_row(before_row)

    try:
        result = db.execute(update(table).where(pk_column == coerced_id).values(**values).returning(*table.columns))
        row = result.first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="row not found")
        after = _serialize_row(row)
        _record_audit(db, current_admin, table_name, row_id, "update", before=before, after=after)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc.orig))
    return after


@router.delete("/tables/{table_name}/rows/{row_id}")
def delete_row(table_name: str, row_id: str, current_admin: User = Depends(get_current_admin)) -> None:
    """Deliberately unimplemented - see the module docstring. Kept as a
    route (rather than removed outright) so a client hitting it gets an
    explicit, explanatory 403 instead of a generic 404/405."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="hard delete is disabled in the database console. Deactivate the row via an appropriate "
               "status field instead (e.g. a charger's status, a vehicle_request's status), or use that "
               "resource's own dedicated endpoint if one exists.",
    )


@router.get("/audit-log")
def list_audit_log(limit: int = 50, offset: int = 0, table_name: str | None = None,
                    current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
    limit = max(1, min(limit, 200))
    query = select(AdminAuditLog)
    if table_name is not None:
        query = query.where(AdminAuditLog.table_name == table_name)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.execute(
        query.order_by(AdminAuditLog.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    entries = [
        {
            "id": str(r.id), "admin_user_id": str(r.admin_user_id), "table_name": r.table_name,
            "row_id": r.row_id, "action": r.action, "before": r.before, "after": r.after,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return {"entries": entries, "total": total, "limit": limit, "offset": offset}
