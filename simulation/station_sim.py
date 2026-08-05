"""Per-charger SimPy queueing simulation for public DC hubs, highway corridor
stations, and housing-society AC stations.

Each station type gets its own arrival/session distributions, because they
are genuinely different queueing problems (Section 4.2): a public DC hub is
a wait-time problem, a highway corridor is a sparser wait-time problem, and a
housing-society station is a booking/queue problem (few chargers, many
residents holding long overnight sessions).

This module also simulates the reported-vs-verified trust gap the platform
is built to correct: a charger's `status` field can flip to "available"
without a fresh `last_verified_at` — nobody has actually confirmed it works
since. `last_verified_at` only ever refreshes on a genuine verification
event (a vehicle actually starting a session), matching the real-world
failure mode of 25-48% of public DC chargers reporting available while
non-functional.

Each charger/status/{id} message carries full electrical telemetry
(voltage, current, power factor, frequency, temperature, a running energy
meter) alongside status - the same class of readings a real EVSE
controller reports via OCPP MeterValues - so the fault-detection layer
(charger_monitor_sim.py) has real signals to watch rather than a single
status string.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List

import simpy
import simpy.rt

from registry import STATIONS, StationSpec

logging.basicConfig(level=logging.INFO, format="%(asctime)s station-sim %(message)s")
log = logging.getLogger("station-sim")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
REALTIME_FACTOR = float(os.environ.get("STATION_SIM_REALTIME_FACTOR", "1.0"))
FLAKY_CHARGER_RATE = float(os.environ.get("FLAKY_CHARGER_RATE", "0.25"))
# Mid-session electrical readings are published on this cadence (sim
# minutes) in addition to every status transition, matching how a real
# EVSE controller sends periodic OCPP MeterValues rather than only
# reporting on start/stop - without this, energy_delivered_kwh would only
# ever be visible as a single final total.
TELEMETRY_TICK_MINUTES = 2.0

AMBIENT_TEMP_C = 32.0  # typical Vellore ambient
CHARGER_POWER_FACTOR = 0.98
GRID_FREQUENCY_HZ = 50.0

# (mean_interarrival_minutes, mean_session_minutes, offline_probability, mean_offline_minutes)
STATION_PROFILES: Dict[str, tuple[float, float, float, float]] = {
    "public_dc_hub": (6.0, 20.0, 0.05, 45.0),
    "highway_corridor": (12.0, 18.0, 0.04, 60.0),
    "housing_society_ac": (25.0, 300.0, 0.02, 120.0),
}

PublishFn = Callable[[dict], None]


def _nominal_voltage_v(charger_power_kw: float) -> float:
    """DC fast chargers run higher bus voltages as rated power climbs (real
    CCS2 architectures), AC chargers are single-phase 230V - matches Indian
    LV distribution (IS 12360)."""
    if charger_power_kw <= 22.0:
        return 230.0  # single-phase AC (Type 2 / IEC 62196), e.g. 7.4 kW = 230V x 32A
    if charger_power_kw <= 60.0:
        return 400.0  # DC fast charging, lower power tier
    return 650.0  # DC fast charging, higher power tier (CCS2 up to ~150kW class)


@dataclass
class ChargerState:
    index: int
    status: str = "available"
    last_verified_at: str = ""
    flaky: bool = False
    session_start_sim_time: float = 0.0
    temperature_c: float = AMBIENT_TEMP_C


@dataclass
class Station:
    env: simpy.Environment
    spec: StationSpec
    publish: PublishFn
    chargers: List[ChargerState] = field(default_factory=list)
    free_indices: List[int] = field(default_factory=list)
    resource: simpy.Resource = field(init=False)

    def __post_init__(self) -> None:
        self.resource = simpy.Resource(self.env, capacity=self.spec.num_chargers)
        for i in range(self.spec.num_chargers):
            flaky = random.random() < FLAKY_CHARGER_RATE
            self.chargers.append(ChargerState(index=i, flaky=flaky))
            self.free_indices.append(i)
        for charger in self.chargers:
            self._publish_charger(charger, verified=True)

    def _publish_charger(self, charger: ChargerState, verified: bool, event_type: str = "StatusNotification") -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if verified or not charger.last_verified_at:
            charger.last_verified_at = now_iso
        occupied = charger.status == "occupied"
        rated_kw = self.spec.charger_power_kw
        power_kw = rated_kw if occupied else 0.0
        voltage_v = _nominal_voltage_v(rated_kw) + random.uniform(-1.5, 1.5)
        current_a = (power_kw * 1000.0) / (voltage_v * CHARGER_POWER_FACTOR) if occupied else round(random.uniform(0.02, 0.08), 3)
        # First-order approach toward a load-dependent target temperature -
        # a reasonable approximation of thermal lag, not a full RC thermal
        # model, but enough to give the fault-detection layer (§6) a signal
        # that rises gradually under load and cools when idle, rather than
        # jumping instantly.
        target_temp = AMBIENT_TEMP_C + (power_kw / rated_kw) * 18.0 if occupied else AMBIENT_TEMP_C
        charger.temperature_c += (target_temp - charger.temperature_c) * 0.4
        energy_delivered_kwh = 0.0
        if occupied:
            elapsed_hours = max(0.0, self.env.now - charger.session_start_sim_time) / 60.0
            energy_delivered_kwh = round(rated_kw * elapsed_hours, 3)
        self.publish({
            "charger_id": f"{self.spec.station_id}-charger-{charger.index}",
            "station_id": self.spec.station_id,
            "station_type": self.spec.station_type,
            "feeder_id": self.spec.feeder_id,
            "status": charger.status,
            # OCPP-style split: StatusNotification marks an actual state
            # transition (start/stop/offline/available - one per session
            # event), MeterValues is a periodic mid-session reading. Keeping
            # them distinguishable matters: a MeterValues tick reporting
            # status="occupied" mid-session is not itself a fresh
            # verification of the charger, unlike the StatusNotification
            # that started the session.
            "event_type": event_type,
            "power_kw": power_kw,
            "rated_power_kw": rated_kw,
            "voltage_v": round(voltage_v, 1),
            "current_a": round(current_a, 2),
            "power_factor": CHARGER_POWER_FACTOR if occupied else 0.0,
            "frequency_hz": round(GRID_FREQUENCY_HZ + random.uniform(-0.02, 0.02), 3),
            "temperature_c": round(charger.temperature_c, 1),
            "energy_delivered_kwh": energy_delivered_kwh,
            "last_verified_at": charger.last_verified_at,
            "reported_at": now_iso,
        })

    def charger_telemetry_ticker(self, charger: ChargerState) -> simpy.events.ProcessGenerator:
        """Periodic mid-session electrical readings, matching how a real
        EVSE controller sends OCPP MeterValues every 30-300s during a
        session rather than only reporting at start/stop - without this,
        energy_delivered_kwh/temperature_c would only ever be visible as a
        single value at the very end of a session."""
        while charger.status == "occupied":
            yield self.env.timeout(TELEMETRY_TICK_MINUTES)
            if charger.status == "occupied":
                self._publish_charger(charger, verified=False, event_type="MeterValues")

    def vehicle_session(self) -> simpy.events.ProcessGenerator:
        _, mean_session, offline_prob, mean_offline = STATION_PROFILES[self.spec.station_type]
        with self.resource.request() as req:
            yield req
            idx = self.free_indices.pop()
            charger = self.chargers[idx]
            charger.status = "occupied"
            charger.session_start_sim_time = self.env.now
            self._publish_charger(charger, verified=True)
            self.env.process(self.charger_telemetry_ticker(charger))

            duration = max(2.0, random.expovariate(1.0 / mean_session))
            yield self.env.timeout(duration)

            if random.random() < offline_prob:
                charger.status = "offline"
                self._publish_charger(charger, verified=True)
                yield self.env.timeout(max(5.0, random.expovariate(1.0 / mean_offline)))
                charger.status = "available"
                self._publish_charger(charger, verified=True)
            else:
                charger.status = "available"
                verified = not (charger.flaky and random.random() < 0.6)
                self._publish_charger(charger, verified=verified)

            self.free_indices.append(idx)

    def arrivals(self) -> simpy.events.ProcessGenerator:
        mean_interarrival, *_ = STATION_PROFILES[self.spec.station_type]
        while True:
            yield self.env.timeout(random.expovariate(1.0 / mean_interarrival))
            self.env.process(self.vehicle_session())


def build_stations(env: simpy.Environment, publish: PublishFn, specs: List[StationSpec] = STATIONS) -> List[Station]:
    stations = [Station(env=env, spec=spec, publish=publish) for spec in specs]
    for station in stations:
        env.process(station.arrivals())
    return stations


def main() -> None:
    import paho.mqtt.client as mqtt

    from sim_seed import apply_random_seed
    apply_random_seed("station-sim")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)
    client.loop_start()

    def publish(payload: dict) -> None:
        client.publish(f"charger/status/{payload['charger_id']}", json.dumps(payload), qos=0)

    env = simpy.rt.RealtimeEnvironment(factor=REALTIME_FACTOR, strict=False)
    stations = build_stations(env, publish)
    log.info("station-sim running %d stations (%d chargers total)",
              len(stations), sum(s.spec.num_chargers for s in stations))
    env.run()


if __name__ == "__main__":
    main()
