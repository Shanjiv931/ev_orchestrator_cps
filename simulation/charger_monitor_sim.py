"""Simulated embedded charger fault-detection layer (Charger Monitoring
Unit, CMU).

Modeled as a lightweight embedded controller - conceptually equivalent to
an ESP32/STM32-class microcontroller reading, per port: a current-sense
shunt resistor, an NTC thermistor, a voltage divider, an RCD-style earth-
leakage sense line, the IEC 61851 Control Pilot/Proximity Pilot signal
pair (connection/charging handshake), and its own cellular/WiFi modem's
signal strength - running a local threshold state machine and reporting
real, industry-standard OCPP StatusNotification ErrorCode values upstream
(ConnectorLockFailure, EVCommunicationError, GroundFailure, HighTemperature,
InternalError, OverCurrentFailure, OverVoltage, PowerMeterFailure,
PowerSwitchFailure, ReaderFailure, UnderVoltage, WeakSignal, NoError), not
invented fault codes. Implemented here as a software simulation, not
physical hardware - this project has a standing "no physical hardware,
simulate every output" rule (docs/out-of-scope.md Section 2) - but the
sensor suite, fault taxonomy, debounce logic, and periodic heartbeat all
mirror a real EVSE controller's actual behavior.

This module WATCHES the electrical telemetry station_sim.py already
publishes on charger/status/{id} (voltage_v, current_a, temperature_c,
power_kw, status) rather than re-simulating a charger's physics - matching
how a real monitoring IC watches sensor lines independently of the
power-delivery hardware it's monitoring, not duplicating it. On a
detected, debounced fault it publishes charger/fault/{id}; when healthy it
still publishes a periodic NoError heartbeat, so a consumer can tell
"monitored and healthy" apart from "not reporting at all" - itself a
meaningful signal (see backend/app/services/fault_consumer.py).

Fault injection (rate controlled by the active scenario's
fault_injection_rate axis, backend/app/scenario_engine.py, broadcast over
MQTT as scenario/active) perturbs the readings this module evaluates for a
bounded duration, on top of whatever organic extremes real load already
produces - so "degraded station" scenarios reliably demonstrate detection
without depending on rare organic occurrences.
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s charger-monitor %(message)s")
log = logging.getLogger("charger-monitor")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

VOLTAGE_TOLERANCE = 0.10  # +-10% of nominal, standard EN 50160 LV supply tolerance
CURRENT_OVERLOAD_FACTOR = 1.15
DC_TEMP_LIMIT_C = 70.0
AC_TEMP_LIMIT_C = 60.0
ZERO_CURRENT_DEBOUNCE_TICKS = 3  # consecutive "occupied but no current" readings before PowerMeterFailure
FAULT_DEBOUNCE_TICKS = 2  # consecutive threshold breaches required before reporting (avoid single-tick noise)
HEARTBEAT_INTERVAL_S = 120.0

FAULT_INJECTION_RATE = {"off": 0.0, "baseline": 0.0006, "elevated": 0.003}
FAULT_DURATION_RANGE_S = (60.0, 300.0)

# Ground-fault (earth leakage) detection - IEC 61851 mandates an RCD-style
# trip well below 30mA. Backed by a real synthetic reading (ground_leakage_ma)
# rather than a discrete label-only event, like the electrical thresholds
# above it.
GROUND_LEAKAGE_TRIP_MA = 30.0

# Cellular/WiFi backhaul signal - a genuinely different failure surface
# from the charger's own electronics, and realistically worse at exposed
# highway-corridor/rural sites than urban DC hubs (site type read straight
# off the charger/status payload's station_type field).
SIGNAL_BASELINE_PCT = {
    "public_dc_hub": 90.0, "housing_society_ac": 85.0, "highway_corridor": 65.0,
}
WEAK_SIGNAL_THRESHOLD_PCT = 40.0

# (error_code, severity) - GroundFailure/ConnectorLockFailure/ReaderFailure/
# PowerSwitchFailure/InternalError don't perturb a specific threshold-
# checked reading (they represent insulation, physical/tamper, payment-
# reader, contactor, and generic electronics failures respectively) so
# they surface directly while injected rather than via a threshold check.
INJECTABLE_FAULTS = [
    ("OverCurrentFailure", "critical"),
    ("OverVoltage", "critical"),
    ("UnderVoltage", "warning"),
    ("HighTemperature", "critical"),
    ("GroundFailure", "critical"),
    ("ConnectorLockFailure", "warning"),  # tamper/physical-fault category (forced disconnect, vandalism)
    ("ReaderFailure", "warning"),  # RFID/payment reader malfunction
    ("PowerSwitchFailure", "critical"),  # contactor/relay failed to engage or disengage
    ("WeakSignal", "warning"),
    ("InternalError", "warning"),
]

# IEC 61851 Control Pilot states - the actual signal a real EVSE
# microcontroller reads to know connection/charging state, more granular
# than a bare "available/occupied/offline" status string.
PILOT_STATE_NO_VEHICLE = "A"       # no vehicle connected
PILOT_STATE_CONNECTED = "B"        # vehicle connected, not drawing power
PILOT_STATE_CHARGING = "C"         # vehicle connected and charging
PILOT_STATE_FAULT = "F"            # pilot circuit fault


def _nominal_voltage_v(charger_power_kw: float) -> float:
    if charger_power_kw <= 22.0:
        return 230.0
    if charger_power_kw <= 60.0:
        return 400.0
    return 650.0


def _pilot_state(status: str, active_fault: Optional[str]) -> str:
    if active_fault in ("GroundFailure", "PowerSwitchFailure"):
        return PILOT_STATE_FAULT
    if status == "occupied":
        return PILOT_STATE_CHARGING
    if status == "offline":
        return PILOT_STATE_FAULT
    return PILOT_STATE_NO_VEHICLE


@dataclass
class ChargerMonitorState:
    zero_current_ticks: int = 0
    fault_streak: Dict[str, int] = field(default_factory=dict)
    active_injected_fault: Optional[str] = None
    active_injected_severity: str = "warning"
    injected_fault_expires_at: float = 0.0
    last_report_at: float = 0.0
    signal_baseline_pct: float = 85.0
    # Latest computed sensor readings not carried in the incoming payload -
    # stashed here so publish() can include them regardless of whether this
    # tick reported a fault or a heartbeat.
    last_ground_leakage_ma: float = 0.0
    last_signal_strength_pct: float = 90.0
    last_pilot_state: str = PILOT_STATE_NO_VEHICLE


class FaultInjectionRate:
    """Live fault_injection_rate axis from the active scenario."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rate_key = "baseline"

    def update(self, rate_key: str) -> None:
        with self._lock:
            self._rate_key = rate_key if rate_key in FAULT_INJECTION_RATE else "baseline"

    def current_rate(self) -> float:
        with self._lock:
            return FAULT_INJECTION_RATE[self._rate_key]


def _on_scenario_message(injection_rate: FaultInjectionRate):
    def _handler(_client, _userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        injection_rate.update(payload.get("fault_injection_rate", "baseline"))

    return _handler


def evaluate(state: ChargerMonitorState, payload: dict, injection_rate: FaultInjectionRate) -> Optional[tuple[str, str]]:
    """Returns (error_code, severity) if a debounced fault should be
    reported this tick, else None (healthy or not yet debounced)."""
    now = time.time()
    rated_kw = float(payload.get("rated_power_kw") or payload.get("power_kw") or 0.0)
    nominal_v = _nominal_voltage_v(rated_kw)
    temp_limit = DC_TEMP_LIMIT_C if rated_kw > 22.0 else AC_TEMP_LIMIT_C
    rated_current_a = (rated_kw * 1000.0) / (nominal_v * 0.98) if rated_kw > 0 else 0.0

    voltage_v = float(payload.get("voltage_v", nominal_v))
    current_a = float(payload.get("current_a", 0.0))
    temperature_c = float(payload.get("temperature_c", 30.0))
    status = payload.get("status", "available")
    state.signal_baseline_pct = SIGNAL_BASELINE_PCT.get(payload.get("station_type", ""), 85.0)

    if state.active_injected_fault and now >= state.injected_fault_expires_at:
        state.active_injected_fault = None

    if state.active_injected_fault is None and random.random() < injection_rate.current_rate():
        code, severity = random.choice(INJECTABLE_FAULTS)
        state.active_injected_fault = code
        state.active_injected_severity = severity
        state.injected_fault_expires_at = now + random.uniform(*FAULT_DURATION_RANGE_S)
        log.info("injecting %s into %s for %.0fs", code, payload.get("charger_id"), state.injected_fault_expires_at - now)

    if state.active_injected_fault == "OverCurrentFailure":
        current_a *= 1.4
    elif state.active_injected_fault == "OverVoltage":
        voltage_v *= 1.18
    elif state.active_injected_fault == "UnderVoltage":
        voltage_v *= 0.85
    elif state.active_injected_fault == "HighTemperature":
        temperature_c += 28.0

    # Ground leakage (RCD) - near-zero under normal insulation, a real
    # earth fault spikes it well past the IEC 61851 trip threshold.
    ground_leakage_ma = random.uniform(0.0, 2.0)
    if state.active_injected_fault == "GroundFailure":
        ground_leakage_ma = random.uniform(35.0, 60.0)
    state.last_ground_leakage_ma = round(ground_leakage_ma, 2)

    # Backhaul signal strength - site-type baseline (highway/rural sites
    # are realistically weaker) plus noise, degraded further when injected.
    signal_strength_pct = state.signal_baseline_pct + random.uniform(-5.0, 5.0)
    if state.active_injected_fault == "WeakSignal":
        signal_strength_pct = random.uniform(5.0, 25.0)
    state.last_signal_strength_pct = round(max(0.0, min(100.0, signal_strength_pct)), 1)
    state.last_pilot_state = _pilot_state(status, state.active_injected_fault)

    detected: Optional[tuple[str, str]] = None
    if rated_current_a > 0 and current_a > rated_current_a * CURRENT_OVERLOAD_FACTOR:
        detected = ("OverCurrentFailure", "critical")
    elif voltage_v > nominal_v * (1 + VOLTAGE_TOLERANCE):
        detected = ("OverVoltage", "critical")
    elif voltage_v < nominal_v * (1 - VOLTAGE_TOLERANCE):
        detected = ("UnderVoltage", "warning")
    elif temperature_c > temp_limit:
        detected = ("HighTemperature", "critical")
    elif state.last_ground_leakage_ma > GROUND_LEAKAGE_TRIP_MA:
        detected = ("GroundFailure", "critical")
    elif state.last_signal_strength_pct < WEAK_SIGNAL_THRESHOLD_PCT:
        detected = ("WeakSignal", "warning")
    elif state.active_injected_fault in ("ConnectorLockFailure", "ReaderFailure", "PowerSwitchFailure", "InternalError"):
        detected = (state.active_injected_fault, state.active_injected_severity)

    if status == "occupied" and current_a < 0.5:
        state.zero_current_ticks += 1
        if state.zero_current_ticks >= ZERO_CURRENT_DEBOUNCE_TICKS:
            detected = ("PowerMeterFailure", "critical")
    else:
        state.zero_current_ticks = 0

    code = detected[0] if detected else None
    for existing_code in list(state.fault_streak):
        if existing_code != code:
            state.fault_streak[existing_code] = 0
    if code:
        state.fault_streak[code] = state.fault_streak.get(code, 0) + 1
        if state.fault_streak[code] >= FAULT_DEBOUNCE_TICKS:
            state.last_report_at = now
            return detected

    if now - state.last_report_at > HEARTBEAT_INTERVAL_S:
        state.last_report_at = now
        return ("NoError", "info")
    return None


def on_charger_status(states: Dict[str, ChargerMonitorState], injection_rate: FaultInjectionRate, publish):
    def _handler(_client, _userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        charger_id = payload.get("charger_id")
        if not charger_id:
            return
        state = states.setdefault(charger_id, ChargerMonitorState())
        result = evaluate(state, payload, injection_rate)
        if result is None:
            return
        error_code, severity = result
        publish(charger_id, payload.get("station_id", ""), error_code, severity, payload, state)

    return _handler


def main() -> None:
    from sim_seed import apply_random_seed
    apply_random_seed("charger-monitor")

    states: Dict[str, ChargerMonitorState] = {}
    injection_rate = FaultInjectionRate()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def publish(charger_id: str, station_id: str, error_code: str, severity: str, source: dict, state: ChargerMonitorState) -> None:
        reading = {
            "charger_id": charger_id,
            "station_id": station_id,
            "error_code": error_code,
            "severity": severity,
            "voltage_v": source.get("voltage_v"),
            "current_a": source.get("current_a"),
            "temperature_c": source.get("temperature_c"),
            "ground_leakage_ma": state.last_ground_leakage_ma,
            "signal_strength_pct": state.last_signal_strength_pct,
            "pilot_state": state.last_pilot_state,
            "ts": time.time(),
        }
        client.publish(f"charger/fault/{charger_id}", json.dumps(reading), qos=0)
        if error_code != "NoError":
            log.warning("%s: %s (%s)", charger_id, error_code, severity)

    client.on_message = on_charger_status(states, injection_rate, publish)
    client.message_callback_add("scenario/active", _on_scenario_message(injection_rate))

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)

    client.subscribe("charger/status/#")
    client.subscribe("scenario/active")
    log.info("charger-monitor watching charger/status/# for faults")
    client.loop_forever()


if __name__ == "__main__":
    main()
