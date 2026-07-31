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
    # Existing password accounts predate OTP verification - grandfather them
    # in as verified rather than locking real users out retroactively; only
    # newly-registered accounts start unverified (see models/entities.py).
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code_hash VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS date_of_birth DATE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS license_number VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS license_expiry DATE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS profession VARCHAR",
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
    "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS number_plate VARCHAR",
    "ALTER TABLE chargers ADD COLUMN IF NOT EXISTS port_number INTEGER",
    # Backfill only rows seeded before port_number existed - a stable
    # 1-indexed sequence per station, ordered by id so it's deterministic
    # rather than shuffling on every migration run.
    "UPDATE chargers SET port_number = numbered.rn FROM ("
    "  SELECT id, ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY id) AS rn FROM chargers"
    ") AS numbered WHERE chargers.id = numbered.id AND chargers.port_number IS NULL",
]


def run_lightweight_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        for statement in _STATEMENTS:
            connection.execute(text(statement))
