"""Pydantic request/response schemas, one Create/Read pair per Section 8
entity plus the auth extension (see models/entities.py)."""
import uuid
from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    persona: str
    dpdp_consent_flag: bool = False
    # Required for password registration (see app/routers/auth.py) - not
    # collected at all for Google/Firebase sign-in, which skips UserCreate
    # entirely (Google already gives us name/email, nothing else).
    date_of_birth: date
    phone_number: str
    license_number: str
    license_expiry: date
    profession: str

    @field_validator("date_of_birth")
    @classmethod
    def _must_be_at_least_18(cls, value: date) -> date:
        today = datetime.now(timezone.utc).date()
        age_years = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age_years < 18:
            raise ValueError("must be at least 18 years old to register")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    email: EmailStr
    persona: str
    dpdp_consent_flag: bool
    consent_expiry: datetime | None
    auth_provider: str
    email_verified: bool
    location_state: str | None
    location_city: str | None
    lat: float | None
    lon: float | None
    date_of_birth: date | None
    phone_number: str | None
    license_number: str | None
    license_expiry: date | None
    profession: str | None


class UserUpdate(BaseModel):
    name: str | None = None
    persona: str | None = None
    dpdp_consent_flag: bool | None = None
    consent_expiry: datetime | None = None


class LocationUpdate(BaseModel):
    location_state: str
    location_city: str
    lat: float
    lon: float


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoogleSignInRequest(BaseModel):
    id_token: str


class PendingRegistrationResponse(BaseModel):
    """Returned instead of a TokenResponse - no User row (and therefore no
    valid access token) exists yet until the OTP is verified, see
    app/routers/auth.py."""
    pending_registration_id: str
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    pending_registration_id: str
    otp_code: str


class ResendOtpRequest(BaseModel):
    pending_registration_id: str


class AdminRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    requested_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None


class VehicleCreate(BaseModel):
    vehicle_class: str
    connector_type: str
    battery_chemistry: str
    is_pluggable: bool = True
    fleet_depot_id: str | None = None
    brand: str | None = None
    vehicle_model: str | None = None
    battery_capacity_kwh: float | None = None
    color_hex: str | None = None


class VehicleUpdate(BaseModel):
    connector_type: str | None = None
    battery_chemistry: str | None = None
    is_pluggable: bool | None = None
    fleet_depot_id: str | None = None
    brand: str | None = None
    vehicle_model: str | None = None
    battery_capacity_kwh: float | None = None
    color_hex: str | None = None


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    vehicle_class: str
    connector_type: str
    battery_chemistry: str
    is_pluggable: bool
    fleet_depot_id: str | None
    brand: str | None
    vehicle_model: str | None
    battery_capacity_kwh: float | None
    color_hex: str | None
    is_paired: bool


class VehiclePairingResponse(BaseModel):
    pairing_code: str
    vehicle_id: uuid.UUID


class VehicleLiveTelemetry(BaseModel):
    vehicle_id: uuid.UUID
    is_simulated: bool = True
    battery_pct: float
    is_charging: bool
    range_km: float
    odometer_km: float
    last_updated: datetime


class StationCreate(BaseModel):
    station_type: str
    lat: float
    lon: float
    safety_score: float = 0.0
    has_solar: bool = False


class StationUpdate(BaseModel):
    safety_score: float | None = None
    has_solar: bool | None = None


class ChargerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    station_id: uuid.UUID
    status: str
    last_verified_at: datetime | None
    power_kw: float
    maintenance_risk_score: float


class SwapSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    station_id: uuid.UUID
    status: str
    batteries_available: int


class StationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    station_type: str
    lat: float
    lon: float
    safety_score: float
    has_solar: bool
    chargers: list[ChargerRead] = []
    swap_slots: list[SwapSlotRead] = []


class ChargerCreate(BaseModel):
    status: str = "available"
    power_kw: float
    maintenance_risk_score: float = 0.0


class ChargerMaintenanceCheck(BaseModel):
    total_sessions: int
    aborted_sessions: int
    error_count: int


class ChargerUpdate(BaseModel):
    status: str | None = None
    last_verified_at: datetime | None = None
    maintenance_risk_score: float | None = None


class SwapSlotCreate(BaseModel):
    status: str = "available"
    batteries_available: int = 0


class SwapSlotUpdate(BaseModel):
    status: str | None = None
    batteries_available: int | None = None


class GridFeederCreate(BaseModel):
    station_id: uuid.UUID | None = None
    feeder_zone: str
    capacity_kw: float
    current_load_kw: float = 0.0
    is_rural_minigrid: bool = False


class GridFeederUpdate(BaseModel):
    current_load_kw: float | None = None


class GridFeederRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    station_id: uuid.UUID | None
    feeder_zone: str
    capacity_kw: float
    current_load_kw: float
    is_rural_minigrid: bool


class SessionCreate(BaseModel):
    vehicle_id: uuid.UUID
    charger_id: uuid.UUID | None = None
    is_emergency_priority: bool = False


class SessionUpdate(BaseModel):
    end_time: datetime | None = None
    energy_kwh: float | None = None
    cost: float | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    vehicle_id: uuid.UUID
    charger_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime | None
    energy_kwh: float
    cost: float
    is_emergency_priority: bool


class TelemetryCreate(BaseModel):
    battery_pct: float
    cell_temp_c: float
    power_kw: float


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    session_id: uuid.UUID
    ts: datetime
    battery_pct: float
    cell_temp_c: float
    power_kw: float


class BatteryHealthCreate(BaseModel):
    soh_pct: float
    projected_months_to_80pct: float | None = None
    trend_flag: str = "stable"
    second_life_candidate: str = "no"


class BatteryHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vehicle_id: uuid.UUID
    soh_pct: float
    projected_months_to_80pct: float | None
    trend_flag: str
    second_life_candidate: str
    recorded_at: datetime


class CarbonLedgerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    session_id: uuid.UUID
    co2_avoided_kg: float
    equivalent_fuel_baseline: str
