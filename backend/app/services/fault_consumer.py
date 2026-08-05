"""Consumes charger/fault/{id} (simulation/charger_monitor_sim.py, the
embedded fault-detection layer) and applies it to the real DB-backed
Charger/Station rows in real time - closing the loop from "a fault was
detected" to "the app shows it."

The simulation-layer registry (simulation/registry.py) and the DB-backed
stations table (app/seed_stations.py) are independent datasets with no
shared identifier (docs/out-of-scope.md) - registry.py's 12 real-station
counterparts were deliberately given the same real-world coordinates as
their seed_stations.py originals, so SIMULATION_STATION_COORDS below plus
scenario_engine.find_nearest_station() is what actually correlates a
simulated fault to a real Charger row, the same coordinate-matching
pattern the scenario engine already uses.

Fault counts are tracked in an in-memory rolling window per DB charger
(reset on process restart - acceptable for a live-demo system, a
production deployment would persist this) and fed into the existing
compute_maintenance_risk_score (ml/maintenance_predictor.py) rather than
computing risk a second, different way.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from typing import Dict, List, Tuple

import paho.mqtt.client as mqtt
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Charger, Station
from app.scenario_engine import find_nearest_station
from ml.maintenance_predictor import ChargerTelemetryWindow, compute_maintenance_risk_score

log = logging.getLogger("fault-consumer")

FAULT_WINDOW_SECONDS = 2 * 60 * 60  # 2h rolling window of fault events per charger
CRITICAL_FAULT_STATUS_THRESHOLD = 2  # this many *critical* faults in-window flips Charger.status to "maintenance"

# simulation/registry.py station_id -> the same real Vellore coordinates its
# seed_stations.py counterpart was seeded with (kept in sync manually - see
# module docstring for why this can't be a live join).
SIMULATION_STATION_COORDS: Dict[str, Tuple[float, float]] = {
    "station-vit-dc-01": (12.9698, 79.1559),
    "station-katpadi-dc-01": (12.9686, 79.1352),
    "station-cmc-hospital-dc-01": (12.9186, 79.1354),
    "station-gandhi-nagar-dc-01": (12.9235, 79.1450),
    "station-green-circle-dc-01": (12.9280, 79.1395),
    "station-vellore-fort-hsg-01": (12.9202, 79.1329),
    "station-bagayam-hsg-01": (12.9401, 79.1204),
    "station-sathuvachari-hsg-01": (12.9004, 79.1284),
    "station-officers-line-hsg-01": (12.9150, 79.1370),
    "station-thorapadi-corridor-01": (12.9550, 79.1180),
    "station-chittoor-road-corridor-01": (12.9450, 79.1480),
    "station-arni-road-corridor-01": (12.9080, 79.1500),
    # station-anaicut-village-01 has no real DB counterpart (a rural-outskirts
    # kiosk added purely to preserve the mini-grid scenario type) - faults
    # from it are logged but have no DB row to apply to.
}

CRITICAL_SEVERITY = "critical"
_fault_events: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
_lock = threading.Lock()


def _prune_and_count(db_charger_id: str, now: float) -> Tuple[int, int]:
    with _lock:
        events = [(ts, sev) for ts, sev in _fault_events[db_charger_id] if now - ts <= FAULT_WINDOW_SECONDS]
        _fault_events[db_charger_id] = events
        critical = sum(1 for _, sev in events if sev == CRITICAL_SEVERITY)
        warning = len(events) - critical
        return critical, warning


def _record_event(db_charger_id: str, severity: str, now: float) -> None:
    with _lock:
        _fault_events[db_charger_id].append((now, severity))


def _apply_fault(payload: dict) -> None:
    sim_station_id = payload.get("station_id", "")
    error_code = payload.get("error_code")
    severity = payload.get("severity", "warning")
    if not error_code or error_code == "NoError" or sim_station_id not in SIMULATION_STATION_COORDS:
        return

    lat, lon = SIMULATION_STATION_COORDS[sim_station_id]
    now = time.time()
    with SessionLocal() as db:
        station = find_nearest_station(db, lat, lon)
        if station is None:
            return
        chargers = list(db.execute(select(Charger).where(Charger.station_id == station.id)).scalars())
        if not chargers:
            return

        for charger in chargers:
            db_charger_id = str(charger.id)
            _record_event(db_charger_id, severity, now)
            critical, warning = _prune_and_count(db_charger_id, now)
            window = ChargerTelemetryWindow(
                charger_id=db_charger_id, total_sessions=0, aborted_sessions=0, error_count=0,
                critical_fault_count=critical, warning_fault_count=warning,
            )
            charger.maintenance_risk_score = compute_maintenance_risk_score(window)
            if critical >= CRITICAL_FAULT_STATUS_THRESHOLD and charger.status == "available":
                charger.status = "maintenance"
        station_id_str, charger_count = str(station.id), len(chargers)
        db.commit()
    log.info("applied %s (%s) from %s to station %s (%d chargers updated)",
              error_code, severity, sim_station_id, station_id_str, charger_count)


def get_fault_summary() -> dict:
    """In-window (2h) fault totals across every charger this process has
    seen a fault for, pruned on read - the same window `_apply_fault` uses
    to decide status flips, exposed for the /simulation/report aggregate
    endpoint. Resets on process restart, same caveat as the module docstring."""
    now = time.time()
    with _lock:
        charger_ids = list(_fault_events.keys())
    total_critical = 0
    total_warning = 0
    chargers_with_faults = 0
    for charger_id in charger_ids:
        critical, warning = _prune_and_count(charger_id, now)
        if critical or warning:
            chargers_with_faults += 1
        total_critical += critical
        total_warning += warning
    return {
        "window_seconds": FAULT_WINDOW_SECONDS,
        "critical_fault_count": total_critical,
        "warning_fault_count": total_warning,
        "chargers_with_active_faults": chargers_with_faults,
    }


def _on_message(_client, _userdata, msg: mqtt.MQTTMessage) -> None:
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return
    try:
        _apply_fault(payload)
    except Exception:  # noqa: BLE001 - a single malformed/unexpected fault message must not kill the consumer thread
        log.exception("failed to apply fault message")


def start_fault_consumer() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = _on_message
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.subscribe("charger/fault/#")
    client.loop_start()
    log.info("fault consumer subscribed to charger/fault/#")
    return client
