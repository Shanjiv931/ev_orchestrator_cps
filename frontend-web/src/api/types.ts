export type Persona = "individual_driver" | "fleet_operator" | "housing_society_resident" | "city_admin";

export interface User {
  id: string;
  name: string;
  email: string;
  persona: Persona;
  dpdp_consent_flag: boolean;
  consent_expiry: string | null;
  // "apple-simulated" can still appear on accounts created before Apple
  // Sign-In was removed from the product - kept as a valid display value.
  auth_provider: "password" | "google" | "apple-simulated";
  email_verified: boolean;
  location_state: string | null;
  location_city: string | null;
  lat: number | null;
  lon: number | null;
  date_of_birth: string | null;
  phone_number: string | null;
  license_number: string | null;
  license_expiry: string | null;
  profession: string | null;
}

export interface Vehicle {
  id: string;
  user_id: string;
  vehicle_class: "2W" | "3W" | "4W";
  connector_type: string;
  battery_chemistry: string;
  is_pluggable: boolean;
  fleet_depot_id: string | null;
  brand: string | null;
  vehicle_model: string | null;
  battery_capacity_kwh: number | null;
  color_hex: string | null;
  is_paired: boolean;
  number_plate: string | null;
}

export interface CatalogEntry {
  brand: string;
  vehicle_model: string;
  vehicle_class: "2W" | "3W" | "4W";
  connector_type: string;
  battery_chemistry: string;
  battery_capacity_kwh: number;
  is_pluggable: boolean;
  color_hex: string;
}

export interface MeridianGridLookupResponse {
  meridiangrid_id: string;
  vehicle_class: "2W" | "3W" | "4W";
  connector_type: string;
  battery_chemistry: string;
  is_pluggable: boolean;
  brand: string;
  vehicle_model: string;
  battery_capacity_kwh: number;
  color_hex: string;
}

export interface VehicleRequest {
  id: string;
  ticket_code: string;
  user_id: string;
  request_type: "add" | "delete";
  status: "pending" | "approved" | "rejected";
  meridiangrid_id: string | null;
  number_plate: string | null;
  vehicle_id: string | null;
  reason_code: string | null;
  reason_detail: string | null;
  admin_notes: string | null;
  created_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface VehiclePairingResponse {
  pairing_code: string;
  vehicle_id: string;
}

export interface VehicleLiveTelemetry {
  vehicle_id: string;
  is_simulated: boolean;
  battery_pct: number;
  is_charging: boolean;
  range_km: number;
  odometer_km: number;
  last_updated: string;
}

export interface AdminRequest {
  id: string;
  user_id: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface Charger {
  id: string;
  station_id: string;
  status: string;
  last_verified_at: string | null;
  power_kw: number;
  maintenance_risk_score: number;
  port_number: number | null;
  charger_type: "AC" | "DC";
}

export interface SwapSlot {
  id: string;
  station_id: string;
  status: string;
  batteries_available: number;
}

export interface Station {
  id: string;
  station_type: string;
  lat: number;
  lon: number;
  safety_score: number;
  has_solar: boolean;
  city: string | null;
  chargers: Charger[];
  swap_slots: SwapSlot[];
}

export interface VelloreFleetVehicle {
  vehicle_id: string;
  number_plate: string | null;
  vehicle_class: "2W" | "3W" | "4W";
  brand: string | null;
  vehicle_model: string | null;
  connector_type: string;
  owner_name: string;
  owner_profession: string | null;
  owner_license_number: string | null;
  owner_license_expiry: string | null;
  owner_phone_number: string | null;
  is_paired: boolean;
  battery_pct: number | null;
  is_charging: boolean | null;
}

export interface CrossDistrictCharging {
  vehicle_id: string;
  number_plate: string | null;
  owner_name: string;
  station_id: string;
  station_name: string;
  session_id: string;
  session_start_time: string;
}

export interface ChargingSession {
  id: string;
  user_id: string;
  vehicle_id: string;
  charger_id: string | null;
  start_time: string;
  end_time: string | null;
  energy_kwh: number;
  cost: number;
  is_emergency_priority: boolean;
  payment_status: "unpaid" | "paid";
  payment_method: "upi" | "card" | "cash" | null;
  paid_at: string | null;
}

export interface SessionPayment {
  session_id: string;
  station_id: string | null;
  station_name: string | null;
  cost: number;
  payment_status: "unpaid" | "paid";
  payment_method: "upi" | "card" | "cash" | null;
  paid_at: string | null;
}

export interface BatteryHealth {
  id: string;
  vehicle_id: string;
  soh_pct: number;
  projected_months_to_80pct: number | null;
  trend_flag: string;
  second_life_candidate: string;
  recorded_at: string;
}

export interface GridFeeder {
  id: string;
  station_id: string | null;
  feeder_zone: string;
  capacity_kw: number;
  current_load_kw: number;
  is_rural_minigrid: boolean;
}

export interface TwinEvState {
  vehicle_id: string;
  scenario: string;
  lat: number;
  lon: number;
  speed_kmh: number;
  battery_pct: number;
  vehicle_class: string;
  connector_type: string;
  battery_chemistry: string;
  is_pluggable: boolean;
}

export interface TwinFeederState {
  feeder_id: string;
  feeder_zone: string;
  capacity_kw: number;
  current_load_kw: number;
  loading_percent: number;
  is_overloaded: boolean;
  is_rural_minigrid: boolean;
}
