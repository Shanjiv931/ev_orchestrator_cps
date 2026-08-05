"""Feeder-level grid simulation.

Models each grid feeder (a real Indian distribution transformer serving one
street, one housing society, one highway corridor, or an isolated rural
mini-grid) as its own independent pandapower network. That independence is
the point: a single local transformer can go into overload while every other
feeder in the city stays healthy, which is the real DISCOM failure mode a
single city-wide aggregate model would misrepresent.

Aggregate demand per feeder is driven by real simulated charger/swap-kiosk
load, read from MQTT (published by station_sim.py and swap_sim.py) rather
than a synthetic random signal, so grid stress actually reflects what the
rest of the simulation is doing.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
from typing import Dict

import pandapower as pp
import paho.mqtt.client as mqtt

from registry import FEEDERS, FeederSpec

logging.basicConfig(level=logging.INFO, format="%(asctime)s grid-sim %(message)s")
log = logging.getLogger("grid-sim")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
STEP_SECONDS = float(os.environ.get("GRID_SIM_STEP_SECONDS", "5"))

# Modern power-electronics-based EV chargers (active PFC rectifiers) run
# close to unity but not exactly at it - 0.97 lagging is a realistic
# industry figure, not the physically-impossible 1.0 the load model
# implicitly assumed while q_mvar was hardcoded to 0.
CHARGER_LOAD_POWER_FACTOR = 0.97
NOMINAL_FREQUENCY_HZ = 50.0  # Indian grid nominal (IEGC)


class Feeder:
    """One independent pandapower network representing a single transformer feeder."""

    def __init__(self, spec: FeederSpec) -> None:
        self.spec = spec
        self.net = pp.create_empty_network()
        hv_bus = pp.create_bus(self.net, vn_kv=11.0, name=f"{spec.feeder_id}-hv")
        lv_bus = pp.create_bus(self.net, vn_kv=0.4, name=f"{spec.feeder_id}-lv")
        pp.create_ext_grid(self.net, bus=hv_bus)
        pp.create_transformer_from_parameters(
            self.net,
            hv_bus=hv_bus,
            lv_bus=lv_bus,
            sn_mva=max(spec.capacity_kw, 1.0) / 1000.0 / 0.9,
            vn_hv_kv=11.0,
            vn_lv_kv=0.4,
            vk_percent=6.0,
            vkr_percent=1.5,
            pfe_kw=0.8,
            i0_percent=0.3,
            shift_degree=0,
            name=f"{spec.feeder_id}-transformer",
        )
        self.load_idx = pp.create_load(self.net, bus=lv_bus, p_mw=0.0, q_mvar=0.0, name=f"{spec.feeder_id}-load")

    def step(self, load_kw: float) -> dict:
        p_mw = max(load_kw, 0.0) / 1000.0
        # Real EVSE loads draw reactive power too (PFC-corrected but not
        # perfectly unity) - modeling q_mvar via the assumed power factor
        # instead of leaving it at 0 is what makes the transformer's
        # loading/voltage-drop results physically meaningful rather than
        # just re-deriving current_load_kw/capacity_kw as a percentage.
        q_mvar = p_mw * math.tan(math.acos(CHARGER_LOAD_POWER_FACTOR))
        self.net.load.at[self.load_idx, "p_mw"] = p_mw
        self.net.load.at[self.load_idx, "q_mvar"] = q_mvar
        pp.runpp(self.net, algorithm="nr")
        trafo = self.net.res_trafo.iloc[0]
        loading_percent = float(trafo.loading_percent)
        lv_bus_idx = int(self.net.trafo.at[0, "lv_bus"])
        voltage_lv_pu = float(self.net.res_bus.at[lv_bus_idx, "vm_pu"])
        # A lightweight frequency-deviation heuristic, not a dynamic
        # frequency-domain simulation - real weak/rural feeders do sag
        # slightly under heavy load, and this gives that a visible, bounded
        # signal (49.85-50.00 Hz) without pretending to model generator
        # droop control or AGC.
        frequency_hz = NOMINAL_FREQUENCY_HZ - min(0.15, (loading_percent / 100.0) * 0.15) + random.uniform(-0.01, 0.01)
        return {
            "feeder_id": self.spec.feeder_id,
            "feeder_zone": self.spec.feeder_zone,
            "capacity_kw": self.spec.capacity_kw,
            "current_load_kw": round(load_kw, 2),
            "reactive_power_kvar": round(q_mvar * 1000.0, 2),
            "power_factor": CHARGER_LOAD_POWER_FACTOR,
            "loading_percent": round(loading_percent, 2),
            "is_overloaded": loading_percent > 100.0,
            "is_rural_minigrid": self.spec.is_rural_minigrid,
            "voltage_lv_v": round(voltage_lv_pu * 400.0, 1),
            "voltage_lv_pu": round(voltage_lv_pu, 4),
            "current_lv_a": round(float(trafo.i_lv_ka) * 1000.0, 1),
            "frequency_hz": round(frequency_hz, 3),
            "ts": time.time(),
        }


class GridStressState:
    """Live grid_stress axis from the active scenario (backend/app/
    scenario_engine.py, broadcast over MQTT as scenario/active). "Extreme
    heat drives up AC load across the zone" isn't something any charger/
    swap-kiosk publishes - modeled here as extra non-EV demand layered onto
    the real charger-driven load, so the feeder_overload scenario is
    reliably demonstrable rather than depending on organic charger load
    happening to spike at the moment it's shown."""

    # Additive, not multiplicative: real AC/heat-driven demand doesn't scale
    # with however much EV load happens to exist at that instant (often
    # near-zero, since most chargers are idle most of the time in the
    # SimPy queueing model) - it's independent background load. Sized as a
    # fraction of the feeder's own design capacity so the effect is
    # reliably visible regardless of organic EV load, on every feeder.
    NON_EV_STRESS_FRACTION_OF_CAPACITY = 0.85

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._feeder_overload = False

    def update(self, grid_stress: str) -> None:
        with self._lock:
            self._feeder_overload = grid_stress == "feeder_overload"

    def apply(self, load_kw: float, capacity_kw: float) -> float:
        with self._lock:
            overloaded = self._feeder_overload
        if not overloaded:
            return load_kw
        return load_kw + capacity_kw * self.NON_EV_STRESS_FRACTION_OF_CAPACITY


def _on_scenario_message(stress_state: GridStressState):
    def _handler(_client, _userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        stress_state.update(payload.get("grid_stress", "normal"))

    return _handler


class FeederLoadAggregator:
    """Tracks live power draw per feeder from charger/swap MQTT telemetry.

    charger/status and swap/status payloads carry a feeder_id and a
    power_kw draw (0 when idle/available, > 0 while actively charging).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._draw_by_key: Dict[str, float] = {}
        self._feeder_by_key: Dict[str, str] = {}

    def update(self, key: str, feeder_id: str, power_kw: float) -> None:
        with self._lock:
            self._draw_by_key[key] = power_kw
            self._feeder_by_key[key] = feeder_id

    def total_for_feeder(self, feeder_id: str) -> float:
        with self._lock:
            return sum(
                draw
                for key, draw in self._draw_by_key.items()
                if self._feeder_by_key.get(key) == feeder_id
            )


def on_message(aggregator: FeederLoadAggregator):
    def _handler(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        feeder_id = payload.get("feeder_id")
        power_kw = payload.get("power_kw")
        key = payload.get("charger_id") or payload.get("kiosk_id")
        if feeder_id is None or power_kw is None or key is None:
            return
        aggregator.update(key, feeder_id, float(power_kw))

    return _handler


def main() -> None:
    from sim_seed import apply_random_seed
    apply_random_seed("grid-sim")

    aggregator = FeederLoadAggregator()
    stress_state = GridStressState()
    feeders = {spec.feeder_id: Feeder(spec) for spec in FEEDERS}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message(aggregator)
    client.message_callback_add("scenario/active", _on_scenario_message(stress_state))

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)

    client.subscribe("charger/status/#")
    client.subscribe("swap/status/#")
    client.subscribe("scenario/active")
    client.loop_start()

    log.info("grid-sim running %d independent feeders", len(feeders))
    try:
        while True:
            for feeder_id, feeder in feeders.items():
                load_kw = stress_state.apply(aggregator.total_for_feeder(feeder_id), feeder.spec.capacity_kw)
                reading = feeder.step(load_kw)
                client.publish(f"feeder/load/{feeder_id}", json.dumps(reading), qos=0)
                if reading["is_overloaded"]:
                    log.warning("feeder %s OVERLOADED at %.1f%% (%.1f/%.1f kW)",
                                feeder_id, reading["loading_percent"], reading["current_load_kw"], reading["capacity_kw"])
            time.sleep(STEP_SECONDS)
    finally:
        client.loop_stop()


if __name__ == "__main__":
    main()
