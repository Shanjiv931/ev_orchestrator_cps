export type Persona = "individual_driver" | "fleet_operator" | "housing_society_resident" | "city_admin";

export interface User {
  id: string;
  name: string;
  email: string;
  persona: Persona;
  dpdp_consent_flag: boolean;
  consent_expiry: string | null;
}

export interface Vehicle {
  id: string;
  user_id: string;
  vehicle_class: "2W" | "3W" | "4W";
  connector_type: string;
  battery_chemistry: string;
  is_pluggable: boolean;
  fleet_depot_id: string | null;
}

export interface Charger {
  id: string;
  station_id: string;
  status: string;
  last_verified_at: string | null;
  power_kw: number;
  maintenance_risk_score: number;
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
  chargers: Charger[];
  swap_slots: SwapSlot[];
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
