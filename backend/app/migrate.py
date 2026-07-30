"""Lightweight additive migrations.

This project deliberately uses `Base.metadata.create_all()` instead of
Alembic (see docs/out-of-scope.md) - fine for brand-new tables, but
`create_all()` never alters a table that already exists, so adding columns
to `users`/`vehicles` after the database already has data in them (as
happens here - real accounts already exist) needs an explicit, additive,
idempotent ALTER TABLE step. Every statement uses IF NOT EXISTS and a safe
default so it's a no-op on a fresh database and non-destructive on one with
real rows.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine

_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR NOT NULL DEFAULT 'password'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_subject VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS location_state VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS location_city VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION",
    "DO $$ BEGIN "
    "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_oauth_subject_key') THEN "
    "    ALTER TABLE users ADD CONSTRAINT users_oauth_subject_key UNIQUE (oauth_subject); "
    "  END IF; "
    "END $$",
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS brand VARCHAR",
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS vehicle_model VARCHAR",
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS battery_capacity_kwh DOUBLE PRECISION",
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS color_hex VARCHAR",
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS is_paired BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS pairing_code VARCHAR",
]


def run_lightweight_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        for statement in _STATEMENTS:
            connection.execute(text(statement))
