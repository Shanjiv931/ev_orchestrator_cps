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


class VelloreFleetVehicleRead(BaseModel):
    """One row of the Vellore admin's fleet view (app/routers/admin.py) -
    everything about a Vellore-registered vehicle and its owner the admin
    needs to act on a request or an incident, in one place rather than
    cross-referencing users/vehicles/telemetry by hand."""
    vehicle_id: uuid.UUID
    number_plate: str | None
    vehicle_class: str
    brand: str | None
    vehicle_model: str | None
    connector_type: str
    owner_name: str
    owner_profession: str | None
    owner_license_number: str | None
    owner_license_expiry: date | None
    owner_phone_number: str | None
    is_paired: bool
    battery_pct: float | None
    is_charging: bool | None


class CrossDistrictChargingRead(BaseModel):
    """A non-Vellore-plated vehicle currently mid-session at a Vellore
    station - see app/routers/admin.py. Always empty today since vehicle
    registration is Vellore-plate-only (app/vellore.py), but the query is
    real: if this deployment ever onboards another district, any of its
    vehicles charging on Vellore infrastructure shows up here automatically."""
    vehicle_id: uuid.UUID
    number_plate: str | None
    owner_name: str
    station_id: uuid.UUID
    station_name: str
    session_id: uuid.UUID
    session_start_time: datetime


class AdminRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    requested_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None


class VehicleUpdate(BaseModel):
    fleet_depot_id: str | None = None


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
    number_plate: str | None


class MeridianGridLookupResponse(BaseModel):
    """What "reading the ID off the car" resolves to - shown to the user as
    a preview before they submit an add request, and what the add-request
    approval step (app/routers/admin.py) copies onto the real Vehicle row."""
    meridiangrid_id: str
    vehicle_class: str
    connector_type: str
    battery_chemistry: str
    is_pluggable: bool
    brand: str
    vehicle_model: str
    battery_capacity_kwh: float
    color_hex: str


class VehicleAddRequestCreate(BaseModel):
    meridiangrid_id: str
    number_plate: str


class VehicleDeleteRequestCreate(BaseModel):
    vehicle_id: uuid.UUID
    reason_code: str
    reason_detail: str | None = None


class VehicleRequestReview(BaseModel):
    admin_notes: str | None = None


class VehicleRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ticket_code: str
    user_id: uuid.UUID
    request_type: str
    status: str
    meridiangrid_id: str | None
    number_plate: str | None
    vehicle_id: uuid.UUID | None
    reason_code: str | None
    reason_detail: str | None
    admin_notes: str | None
    created_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None


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
    city: str | None = None


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
    port_number: int | None
    charger_type: str


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
    city: str | None
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
    home_charger_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime | None
    energy_kwh: float
    cost: float
    is_emergency_priority: bool
    payment_status: str
    payment_method: str | None
    paid_at: datetime | None


class StartSessionAtStationRequest(BaseModel):
    vehicle_id: uuid.UUID
    station_id: uuid.UUID


class SessionWithPortRead(SessionRead):
    port_number: int | None


class HomeChargerCreate(BaseModel):
    label: str
    power_kw: float
    # Defaults to the user's own registered home location (User.lat/lon) if
    # omitted - most users have exactly one home and shouldn't have to
    # re-enter coordinates for it.
    lat: float | None = None
    lon: float | None = None


class HomeChargerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    lat: float
    lon: float
    power_kw: float
    installed_at: datetime


class StartHomeSessionRequest(BaseModel):
    vehicle_id: uuid.UUID
    home_charger_id: uuid.UUID


class PoiRead(BaseModel):
    name: str
    poi_type: str
    lat: float
    lon: float
    nearby_station_id: uuid.UUID | None
    nearby_available_chargers: int


class SessionPaymentRead(BaseModel):
    session_id: uuid.UUID
    station_id: uuid.UUID | None
    station_name: str | None
    cost: float
    payment_status: str
    payment_method: str | None
    paid_at: datetime | None


class PaySessionRequest(BaseModel):
    method: str  # "upi" | "card" | "cash"


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
