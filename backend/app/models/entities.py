"""ORM models matching the Section 8 data model exactly, with one documented
extension: USERS gains `email` and `hashed_password` so JWT auth (required by
Section 9.4) has something to authenticate against - the ERD's USERS entity
has no login credential fields at all, so this is the "strictly necessary"
extension the build contract allows for.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    persona: Mapped[str] = mapped_column(String, nullable=False)
    dpdp_consent_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    # "password" | "google"
    auth_provider: Mapped[str] = mapped_column(String, default="password", nullable=False)
    oauth_subject: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # Google accounts start verified (Google already confirmed the email);
    # password accounts start False and must confirm via the OTP emailed on
    # registration - see app/routers/auth.py's /verify-otp.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    otp_code_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location_state: Mapped[str | None] = mapped_column(String, nullable=True)
    location_city: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="user")
    sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="user")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vehicle_class: Mapped[str] = mapped_column(String, nullable=False)  # 2W | 3W | 4W
    connector_type: Mapped[str] = mapped_column(String, nullable=False)
    battery_chemistry: Mapped[str] = mapped_column(String, nullable=False)
    is_pluggable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fleet_depot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String, nullable=True)
    battery_capacity_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String, nullable=True)
    # Simulated vehicle-to-app pairing (Section 5.8-adjacent extension) - no
    # real manufacturer telematics API exists here, see app/routers/vehicle_link.py.
    is_paired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pairing_code: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="vehicles")
    sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="vehicle")
    battery_health: Mapped[list["BatteryHealth"]] = relationship(back_populates="vehicle")


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    station_type: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    has_solar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    chargers: Mapped[list["Charger"]] = relationship(back_populates="station")
    swap_slots: Mapped[list["SwapSlot"]] = relationship(back_populates="station")
    grid_feeders: Mapped[list["GridFeeder"]] = relationship(back_populates="station")


class Charger(Base):
    __tablename__ = "chargers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="available", nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    maintenance_risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    station: Mapped["Station"] = relationship(back_populates="chargers")
    sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="charger")


class SwapSlot(Base):
    __tablename__ = "swap_slots"

    id: Mapped[uuid.UUID] = _uuid_pk()
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="available", nullable=False)
    batteries_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    station: Mapped["Station"] = relationship(back_populates="swap_slots")


class GridFeeder(Base):
    __tablename__ = "grid_feeders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    station_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stations.id"), nullable=True)
    feeder_zone: Mapped[str] = mapped_column(String, nullable=False)
    capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)
    current_load_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_rural_minigrid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    station: Mapped["Station | None"] = relationship(back_populates="grid_feeders")


class ChargingSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    charger_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chargers.id"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_emergency_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")
    vehicle: Mapped["Vehicle"] = relationship(back_populates="sessions")
    charger: Mapped["Charger | None"] = relationship(back_populates="sessions")
    telemetry: Mapped[list["Telemetry"]] = relationship(back_populates="session")
    carbon_ledger_entries: Mapped[list["CarbonLedgerEntry"]] = relationship(back_populates="session")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    battery_pct: Mapped[float] = mapped_column(Float, nullable=False)
    cell_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    power_kw: Mapped[float] = mapped_column(Float, nullable=False)

    session: Mapped["ChargingSession"] = relationship(back_populates="telemetry")


class BatteryHealth(Base):
    __tablename__ = "battery_health"

    id: Mapped[uuid.UUID] = _uuid_pk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    soh_pct: Mapped[float] = mapped_column(Float, nullable=False)
    projected_months_to_80pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_flag: Mapped[str] = mapped_column(String, default="stable", nullable=False)
    second_life_candidate: Mapped[str] = mapped_column(String, default="no", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="battery_health")


class CarbonLedgerEntry(Base):
    __tablename__ = "carbon_ledger"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    co2_avoided_kg: Mapped[float] = mapped_column(Float, nullable=False)
    equivalent_fuel_baseline: Mapped[str] = mapped_column(String, nullable=False)

    session: Mapped["ChargingSession"] = relationship(back_populates="carbon_ledger_entries")


class AdminRequest(Base):
    """Only an existing admin can approve a new admin - no user can grant
    themselves the city_admin persona at registration time."""
    __tablename__ = "admin_requests"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)  # pending | approved | rejected
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])
