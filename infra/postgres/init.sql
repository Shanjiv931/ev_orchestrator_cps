-- Enables the extensions the Section 8 data model depends on.
-- Table creation itself happens in Phase 4 via SQLAlchemy models/migrations.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
