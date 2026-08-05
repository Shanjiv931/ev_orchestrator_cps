"""Static registry of simulated stations, swap kiosks, and the grid feeders
they draw power from.

Shared by every simulator process (station_sim, swap_sim, grid_sim,
solar_sim) so station/feeder IDs and their feeder mapping stay consistent
across independently-running containers that only communicate over MQTT.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StationSpec:
    station_id: str
    station_type: str  # public_dc_hub | highway_corridor | housing_society_ac
    feeder_id: str
    num_chargers: int
    charger_power_kw: float
    has_solar: bool = False


@dataclass(frozen=True)
class SwapKioskSpec:
    kiosk_id: str
    feeder_id: str
    total_batteries: int
    cabinet_power_kw: float
    has_solar: bool = False


@dataclass(frozen=True)
class FeederSpec:
    feeder_id: str
    feeder_zone: str
    capacity_kw: float
    is_rural_minigrid: bool = False


# Vellore, Tamil Nadu - every one of the 12 real stations seeded in
# backend/app/seed_stations.py gets a simulation-layer counterpart here
# (same name/type/has_solar), grouped onto feeders by real zone geography,
# so the simulation registry (what actually publishes live MQTT telemetry)
# and the DB-backed stations table read as the same, complete city - even
# though the two remain independent datasets with no shared identifier
# (see docs/out-of-scope.md). A feeder typically serves several nearby
# stations, matching how a real 11kV/0.4kV zone substation works, rather
# than one feeder per station.
FEEDERS = [
    FeederSpec("feeder-vit-katpadi-dc-01", "VIT-Katpadi DC Hub Zone", capacity_kw=1200.0),
    FeederSpec("feeder-town-core-dc-01", "Vellore Town Core DC Hub Zone", capacity_kw=1200.0),
    FeederSpec("feeder-vellore-fort-hsg-01", "Vellore Fort Housing Society", capacity_kw=80.0),
    FeederSpec("feeder-bagayam-sathuvachari-hsg-01", "Bagayam-Sathuvachari Residential Zone", capacity_kw=120.0),
    FeederSpec("feeder-officers-line-hsg-01", "Officers Line Housing Society", capacity_kw=80.0),
    FeederSpec("feeder-thorapadi-corridor-01", "Thorapadi Highway Corridor", capacity_kw=1200.0),
    FeederSpec("feeder-chittoor-road-corridor-01", "Chittoor Road Highway Corridor", capacity_kw=1000.0),
    FeederSpec("feeder-arni-road-corridor-01", "Arni Road Highway Corridor", capacity_kw=1000.0),
    FeederSpec("feeder-anaicut-village-01", "Anaicut Rural Mini-grid", capacity_kw=25.0, is_rural_minigrid=True),
]

STATIONS = [
    # VIT-Katpadi DC hub zone
    StationSpec("station-vit-dc-01", "public_dc_hub", "feeder-vit-katpadi-dc-01", num_chargers=6, charger_power_kw=80.0),
    StationSpec("station-katpadi-dc-01", "public_dc_hub", "feeder-vit-katpadi-dc-01", num_chargers=3, charger_power_kw=60.0),
    # Vellore town core DC hub zone
    StationSpec("station-cmc-hospital-dc-01", "public_dc_hub", "feeder-town-core-dc-01", num_chargers=4, charger_power_kw=75.0),
    StationSpec("station-gandhi-nagar-dc-01", "public_dc_hub", "feeder-town-core-dc-01", num_chargers=3, charger_power_kw=60.0),
    StationSpec("station-green-circle-dc-01", "public_dc_hub", "feeder-town-core-dc-01", num_chargers=3, charger_power_kw=60.0),
    # Housing-society AC zones
    StationSpec("station-vellore-fort-hsg-01", "housing_society_ac", "feeder-vellore-fort-hsg-01", num_chargers=3, charger_power_kw=7.4, has_solar=True),
    StationSpec("station-bagayam-hsg-01", "housing_society_ac", "feeder-bagayam-sathuvachari-hsg-01", num_chargers=4, charger_power_kw=7.4, has_solar=True),
    StationSpec("station-sathuvachari-hsg-01", "housing_society_ac", "feeder-bagayam-sathuvachari-hsg-01", num_chargers=3, charger_power_kw=7.4),
    StationSpec("station-officers-line-hsg-01", "housing_society_ac", "feeder-officers-line-hsg-01", num_chargers=3, charger_power_kw=7.4, has_solar=True),
    # Highway corridor stations
    StationSpec("station-thorapadi-corridor-01", "highway_corridor", "feeder-thorapadi-corridor-01", num_chargers=5, charger_power_kw=120.0),
    StationSpec("station-chittoor-road-corridor-01", "highway_corridor", "feeder-chittoor-road-corridor-01", num_chargers=4, charger_power_kw=120.0),
    StationSpec("station-arni-road-corridor-01", "highway_corridor", "feeder-arni-road-corridor-01", num_chargers=4, charger_power_kw=120.0),
    # Village outskirts kiosk - not one of the 12 DB-seeded stations, kept
    # to preserve the rural-mini-grid scenario type (a single small station
    # can dominate a rural feeder's capacity, unlike any urban zone above).
    StationSpec("station-anaicut-village-01", "housing_society_ac", "feeder-anaicut-village-01", num_chargers=2, charger_power_kw=3.3, has_solar=True),
]

SWAP_KIOSKS = [
    SwapKioskSpec("swap-vit-01", "feeder-vit-katpadi-dc-01", total_batteries=20, cabinet_power_kw=15.0),
    SwapKioskSpec("swap-chittoor-road-corridor-01", "feeder-chittoor-road-corridor-01", total_batteries=30, cabinet_power_kw=15.0),
]

FEEDERS_BY_ID = {f.feeder_id: f for f in FEEDERS}
STATIONS_BY_ID = {s.station_id: s for s in STATIONS}
SWAP_KIOSKS_BY_ID = {k.kiosk_id: k for k in SWAP_KIOSKS}
