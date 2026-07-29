"""TraCI bridge: drives a SUMO scenario (city or highway corridor) and
publishes each vehicle's live state as ev/telemetry/{id} MQTT messages.

Each SUMO vehicle is deterministically mapped onto an EV profile (vehicle
class, connector type, battery chemistry, pluggable flag - Section 4.1) so
telemetry looks like a real heterogeneous Indian EV fleet rather than one
vehicle type repeated. A per-vehicle simulated battery depletes with
distance travelled, so the corridor scenario visibly drives battery_pct
toward empty over a long, sparsely-chargered route - the range-anxiety
demonstration required by Section 4.4.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s traci-bridge %(message)s")
log = logging.getLogger("traci-bridge")

SUMO_HOME = os.environ.get("SUMO_HOME", "/usr/share/sumo")
sys.path.append(os.path.join(SUMO_HOME, "tools"))

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

VEHICLE_CLASSES = ["2W", "3W", "4W"]
CONNECTOR_BY_CLASS = {
    "2W": ["swap-cassette", "Bharat AC-001"],
    "3W": ["swap-cassette", "Bharat AC-001"],
    "4W": ["Bharat DC-001", "CCS2", "Type 2"],
}
CHEMISTRY_BY_CLASS = {
    "2W": ["LFP", "lead-acid"],
    "3W": ["LFP", "lead-acid"],
    "4W": ["NMC", "LFP"],
}
BATTERY_CAPACITY_KWH_BY_CLASS = {"2W": 3.0, "3W": 5.0, "4W": 40.0}
CONSUMPTION_KWH_PER_KM_BY_CLASS = {"2W": 0.03, "3W": 0.06, "4W": 0.15}
NON_PLUGGABLE_RATE = 0.08  # a slice of simulated "EVs" are non-plug-in hybrids


def _hash_pick(vehicle_id: str, salt: str, options: List[str]) -> str:
    digest = hashlib.sha256(f"{vehicle_id}:{salt}".encode()).hexdigest()
    return options[int(digest, 16) % len(options)]


@dataclass
class VehicleProfile:
    vehicle_class: str
    connector_type: str
    battery_chemistry: str
    is_pluggable: bool
    battery_capacity_kwh: float
    consumption_kwh_per_km: float
    battery_pct: float = 90.0


def build_profile(vehicle_id: str) -> VehicleProfile:
    vclass = _hash_pick(vehicle_id, "class", VEHICLE_CLASSES)
    connector = _hash_pick(vehicle_id, "connector", CONNECTOR_BY_CLASS[vclass])
    chemistry = _hash_pick(vehicle_id, "chemistry", CHEMISTRY_BY_CLASS[vclass])
    digest = int(hashlib.sha256(f"{vehicle_id}:pluggable".encode()).hexdigest(), 16)
    is_pluggable = (digest % 100) >= int(NON_PLUGGABLE_RATE * 100)
    initial_pct = 60 + (digest % 35)  # start between 60-95%
    return VehicleProfile(
        vehicle_class=vclass,
        connector_type=connector,
        battery_chemistry=chemistry,
        is_pluggable=is_pluggable,
        battery_capacity_kwh=BATTERY_CAPACITY_KWH_BY_CLASS[vclass],
        consumption_kwh_per_km=CONSUMPTION_KWH_PER_KM_BY_CLASS[vclass],
        battery_pct=float(initial_pct),
    )


def deplete_battery(profile: VehicleProfile, distance_km: float) -> None:
    energy_used_kwh = distance_km * profile.consumption_kwh_per_km
    pct_used = (energy_used_kwh / profile.battery_capacity_kwh) * 100.0
    profile.battery_pct = max(0.0, profile.battery_pct - pct_used)


def build_telemetry(traci_module, scenario_name: str, vehicle_id: str, profile: VehicleProfile, step_length: float) -> dict:
    speed_m_s = traci_module.vehicle.getSpeed(vehicle_id)
    deplete_battery(profile, distance_km=(speed_m_s * step_length) / 1000.0)
    lon, lat = traci_module.simulation.convertGeo(*traci_module.vehicle.getPosition(vehicle_id))
    return {
        "vehicle_id": f"{scenario_name}-{vehicle_id}",
        "scenario": scenario_name,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "speed_kmh": round(speed_m_s * 3.6, 1),
        "battery_pct": round(profile.battery_pct, 1),
        "vehicle_class": profile.vehicle_class,
        "connector_type": profile.connector_type,
        "battery_chemistry": profile.battery_chemistry,
        "is_pluggable": profile.is_pluggable,
        "ts": time.time(),
    }


def run(sumocfg_path: str, scenario_name: str, mqtt_client, step_length: float = 1.0,
        realtime_factor: float = 1.0) -> None:
    """realtime_factor > 0 paces steps to wall-clock time (1.0 = one
    step_length of simulated time per step_length seconds of real time), so
    the "live" twin actually tracks real time and doesn't flood MQTT/the
    twin-engine with messages faster than anything downstream can consume.
    Set to 0 to run uncapped (e.g. for scenario validation)."""
    import traci

    traci.start(["sumo", "-c", sumocfg_path, "--step-length", str(step_length), "--no-warnings", "true"])
    profiles: Dict[str, VehicleProfile] = {}

    try:
        step = 0
        next_deadline = time.monotonic()
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            for vehicle_id in traci.vehicle.getIDList():
                if vehicle_id not in profiles:
                    profiles[vehicle_id] = build_profile(vehicle_id)
                payload = build_telemetry(traci, scenario_name, vehicle_id, profiles[vehicle_id], step_length)
                mqtt_client.publish(f"ev/telemetry/{payload['vehicle_id']}", json.dumps(payload), qos=0)

            step += 1
            if step % 100 == 0:
                log.info("%s: step %d, %d active vehicles", scenario_name, step, len(traci.vehicle.getIDList()))

            if realtime_factor > 0:
                next_deadline += step_length / realtime_factor
                sleep_for = next_deadline - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    next_deadline = time.monotonic()  # fell behind; don't try to catch up in a burst
    finally:
        traci.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["city", "corridor"])
    parser.add_argument("--sumocfg", required=True)
    parser.add_argument("--step-length", type=float, default=1.0)
    parser.add_argument("--realtime-factor", type=float, default=1.0)
    args = parser.parse_args()

    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)
    client.loop_start()

    log.info("starting %s scenario from %s", args.scenario, args.sumocfg)
    while True:
        run(args.sumocfg, args.scenario, client, step_length=args.step_length,
            realtime_factor=args.realtime_factor)
        log.info("%s scenario finished, restarting for a continuous live demo", args.scenario)


if __name__ == "__main__":
    main()
