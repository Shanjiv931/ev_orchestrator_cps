"""Generic admin database browser/editor - lists every table in the schema
(derived straight from Base.metadata, so it can never drift out of sync
with the actual models) and does raw CRUD against any of them by primary
key. Deliberately not model-specific: this is a dev/ops tool for the
Vellore admin to inspect and fix data directly, not a business-logic
endpoint, so it bypasses the validation each resource's own router
enforces (e.g. Vellore-plate checks, OTP-gated user creation) on purpose -
that's the whole point of a raw database console, but it's exactly why
this stays admin-only.
"""
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import Table, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import Base, get_db
from app.models import User

router = APIRouter(prefix="/admin/db", tags=["admin-database"])


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
        tables.append({"name": table.name, "row_count": row_count, "columns": columns})
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
    values = _coerce_payload(table, payload)
    try:
        result = db.execute(insert(table).values(**values).returning(*table.columns))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc.orig))
    return _serialize_row(result.one())


@router.patch("/tables/{table_name}/rows/{row_id}")
def update_row(table_name: str, row_id: str, payload: dict[str, Any] = Body(...),
               current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
    table = _get_table(table_name)
    pk_column = _primary_key_column(table)
    values = _coerce_payload(table, payload)
    coerced_id = _coerce_value(pk_column, row_id)
    try:
        result = db.execute(update(table).where(pk_column == coerced_id).values(**values).returning(*table.columns))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc.orig))
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="row not found")
    return _serialize_row(row)


@router.delete("/tables/{table_name}/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_row(table_name: str, row_id: str, current_admin: User = Depends(get_current_admin),
               db: Session = Depends(get_db)) -> None:
    table = _get_table(table_name)
    pk_column = _primary_key_column(table)
    coerced_id = _coerce_value(pk_column, row_id)
    try:
        result = db.execute(delete(table).where(pk_column == coerced_id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"can't delete - other rows still reference it: {exc.orig}",
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="row not found")
