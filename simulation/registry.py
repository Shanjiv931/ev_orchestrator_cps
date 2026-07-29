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


FEEDERS = [
    FeederSpec("feeder-koramangala-dc-01", "Koramangala DC Hub Zone", capacity_kw=1000.0),
    FeederSpec("feeder-indiranagar-hsg-01", "Indiranagar Housing Society", capacity_kw=100.0),
    FeederSpec("feeder-nh48-corridor-01", "NH48 Highway Corridor", capacity_kw=1500.0),
    FeederSpec("feeder-holenarsipura-village-01", "Holenarsipura Rural Mini-grid", capacity_kw=25.0, is_rural_minigrid=True),
]

STATIONS = [
    StationSpec("station-koramangala-dc-01", "public_dc_hub", "feeder-koramangala-dc-01", num_chargers=6, charger_power_kw=60.0),
    StationSpec("station-indiranagar-hsg-01", "housing_society_ac", "feeder-indiranagar-hsg-01", num_chargers=4, charger_power_kw=7.4, has_solar=True),
    StationSpec("station-nh48-corridor-01", "highway_corridor", "feeder-nh48-corridor-01", num_chargers=8, charger_power_kw=120.0),
    StationSpec("station-holenarsipura-village-01", "housing_society_ac", "feeder-holenarsipura-village-01", num_chargers=2, charger_power_kw=3.3, has_solar=True),
]

SWAP_KIOSKS = [
    SwapKioskSpec("swap-koramangala-01", "feeder-koramangala-dc-01", total_batteries=20, cabinet_power_kw=15.0),
    SwapKioskSpec("swap-nh48-corridor-01", "feeder-nh48-corridor-01", total_batteries=30, cabinet_power_kw=15.0),
]

FEEDERS_BY_ID = {f.feeder_id: f for f in FEEDERS}
STATIONS_BY_ID = {s.station_id: s for s in STATIONS}
SWAP_KIOSKS_BY_ID = {k.kiosk_id: k for k in SWAP_KIOSKS}
