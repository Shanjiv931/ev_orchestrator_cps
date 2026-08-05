import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
import paho.mqtt.client as mqtt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Charger, ChargingSession, Station
from app.scenario_engine import SCENARIOS, apply_scenario
from app.schemas import StationRead
from app.services.fault_consumer import get_fault_summary

log = logging.getLogger("simulation")
router = APIRouter(prefix="/simulation", tags=["simulation"])

# One shared, lazily-connected publisher - scenario activation broadcasts a
# `scenario/active` message so the SUMO/registry-driven simulation layer
# (station_sim.py, grid_sim.py, charger_monitor_sim.py, traci_bridge.py) can
# react live (weather/fault-rate/traffic adjustments) without a container
# restart, matching the project's MQTT-first architecture.
_mqtt_client: mqtt.Client | None = None


def _get_mqtt_client() -> mqtt.Client:
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        _mqtt_client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
        _mqtt_client.loop_start()
    return _mqtt_client


class ScenarioSummary(BaseModel):
    id: str
    label: str
    description: str
    traffic: str
    weather: str
    grid_stress: str
    fault_injection_rate: str


class ScenarioApplyRequest(BaseModel):
    scenario_id: str


class ScenarioApplyResponse(BaseModel):
    scenario: ScenarioSummary
    station: StationRead


def _summary(preset) -> ScenarioSummary:
    return ScenarioSummary(
        id=preset.id, label=preset.label, description=preset.description,
        traffic=preset.traffic, weather=preset.weather,
        grid_stress=preset.grid_stress, fault_injection_rate=preset.fault_injection_rate,
    )


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [_summary(s) for s in SCENARIOS.values()]


@router.get("/report")
async def simulation_report(db: Session = Depends(get_db)) -> dict:
    """Live aggregate metrics across the whole platform - queue wait,
    charger utilization, fault-detection activity, energy delivered, and
    feeder overload state - meant to be pulled directly into a paper's
    results/evaluation section rather than hand-assembled from several
    endpoints. Every number here is a real current snapshot (or a 24h
    rolling window, labeled) computed from the same DB rows and live twin
    state the rest of the app reads - nothing here is a separate,
    independently-tracked metric."""
    total_chargers = db.execute(select(func.count()).select_from(Charger)).scalar_one()
    status_counts = dict(db.execute(
        select(Charger.status, func.count()).group_by(Charger.status)
    ).all())
    occupied = status_counts.get("occupied", 0)
    utilization_pct = round((occupied / total_chargers) * 100, 1) if total_chargers else 0.0

    # Mirrors frontend-web/src/components/StationDetailsPanel.tsx's
    # MEAN_SESSION_MINUTES - the two layers communicate only via the shared
    # Station/Charger read model, no cross-import, so this is a deliberate,
    # small, documented duplication (same pattern as SIMULATION_STATION_COORDS).
    mean_session_minutes = {"public_dc_hub": 20, "highway_corridor": 18, "housing_society_ac": 300}
    stations = list(db.execute(select(Station)).scalars().unique())
    queued_waits = []
    total_queued_vehicles = 0
    for station in stations:
        total_queued_vehicles += station.queue_length
        if station.queue_length <= 0:
            continue
        charger_count = max(1, len(station.chargers))
        mean_minutes = mean_session_minutes.get(station.station_type, 25)
        queued_waits.append((station.queue_length * mean_minutes) / charger_count)
    avg_estimated_wait_minutes = round(sum(queued_waits) / len(queued_waits), 1) if queued_waits else None

    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
    energy_row = db.execute(
        select(func.count(), func.coalesce(func.sum(ChargingSession.energy_kwh), 0.0))
        .where(ChargingSession.end_time.is_not(None), ChargingSession.end_time >= window_start)
    ).one()
    sessions_completed_24h, total_energy_kwh_24h = energy_row
    avg_energy_kwh_per_session = round(total_energy_kwh_24h / sessions_completed_24h, 2) if sessions_completed_24h else 0.0

    grid_summary = {"feeders_reporting": 0, "feeders_overloaded": 0, "avg_transformer_loading_pct": None}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.twin_engine_http_url}/state/feeder")
        if response.status_code == status.HTTP_200_OK:
            feeders = list(response.json().values())
            if feeders:
                overloaded = sum(1 for f in feeders if f.get("is_overloaded"))
                loadings = [
                    (f["current_load_kw"] / f["capacity_kw"]) * 100
                    for f in feeders if f.get("capacity_kw")
                ]
                grid_summary = {
                    "feeders_reporting": len(feeders),
                    "feeders_overloaded": overloaded,
                    "avg_transformer_loading_pct": round(sum(loadings) / len(loadings), 1) if loadings else None,
                }
    except httpx.HTTPError:
        log.warning("simulation report: twin-engine feeder state unavailable, omitting grid summary")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chargers": {
            "total": total_chargers,
            "by_status": status_counts,
            "utilization_pct": utilization_pct,
        },
        "queueing": {
            "stations_with_active_queue": len(queued_waits),
            "total_queued_vehicles": total_queued_vehicles,
            "avg_estimated_wait_minutes": avg_estimated_wait_minutes,
        },
        "energy_last_24h": {
            "sessions_completed": sessions_completed_24h,
            "total_energy_kwh": round(total_energy_kwh_24h, 2),
            "avg_energy_kwh_per_session": avg_energy_kwh_per_session,
        },
        "fault_detection": get_fault_summary(),
        "grid": grid_summary,
    }


@router.post("/scenario", response_model=ScenarioApplyResponse)
def activate_scenario(payload: ScenarioApplyRequest, db: Session = Depends(get_db)) -> ScenarioApplyResponse:
    try:
        preset, station = apply_scenario(db, payload.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    client = _get_mqtt_client()
    # Full axis payload, not just the id - downstream sim processes
    # (traci_bridge.py, grid_sim.py, charger_monitor_sim.py) react to these
    # values directly rather than each needing their own copy of SCENARIOS.
    client.publish("scenario/active", json.dumps({
        "scenario_id": preset.id, "traffic": preset.traffic, "weather": preset.weather,
        "grid_stress": preset.grid_stress, "fault_injection_rate": preset.fault_injection_rate,
    }), qos=0, retain=True)
    return ScenarioApplyResponse(scenario=_summary(preset), station=station)
