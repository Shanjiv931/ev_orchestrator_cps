"""API surface for the Section 5 beyond-scope modules that don't already
have a home on an existing resource router: V2G/V2H dispatch, blackout
resilience, solar-synced charging recommendations, the recommendation
scorer (with the safety-score context that must change its output), the
emergency-priority queue, and the mass-gathering stress test. Each wraps
an already-unit-tested `ml/` function; these endpoints are thin so the
underlying logic stays independently testable.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.retention_job import run_retention_sweep
from ml.blackout_resilience import CriticalLoad, plan_emergency_backup
from ml.demand_forecast import ZONES, predict_sessions, train_and_evaluate
from ml.emergency_queue import PriorityJumpTracker, QueuedRequest, insert_with_priority
from ml.event_stress_test import recommend_additional_stations, sweep_density, what_if_all_ev
from ml.recommendation import Candidate, Vehicle, rank_candidates
from ml.solar_sync import recommend_charging_window
from ml.v2g_dispatch import V2GVehicle, dispatch_v2g

router = APIRouter(tags=["advanced-features"])

# In-memory per-process trackers for the stateless demo endpoints below.
# A production deployment would key these per station/swap-point in Redis
# (twin-engine already owns that store) rather than backend process memory.
_priority_jump_trackers: dict[str, PriorityJumpTracker] = {}

# Trained once per process (XGBoost fit takes a couple of seconds); a real
# deployment would retrain on a schedule against real session history
# instead of on first request against synthetic history.
_demand_model_cache: dict = {}


def _get_demand_model():
    if "model" not in _demand_model_cache:
        _demand_model_cache["model"] = train_and_evaluate()
    return _demand_model_cache["model"]


@router.get("/demand-forecast/zones")
def list_forecast_zones() -> list[str]:
    return ZONES


@router.get("/demand-forecast/predict")
def demand_forecast_predict(zone: str, hour: int, day_of_week: int, weather: int = 0) -> dict:
    result = _get_demand_model()
    predicted = predict_sessions(result["model"], zone, hour, day_of_week, weather)
    return {"zone": zone, "hour": hour, "day_of_week": day_of_week, "weather": weather,
            "predicted_sessions": round(predicted, 2), "model_mae": round(result["mae"], 3)}


class V2GVehicleIn(BaseModel):
    id: str
    is_pluggable: bool
    v2g_capable: bool
    opted_in: bool
    is_parked: bool
    soc_pct: float
    battery_capacity_kwh: float
    max_discharge_kw: float


class V2GDispatchRequest(BaseModel):
    vehicles: list[V2GVehicleIn]
    feeder_deficit_kw: float
    duration_hours: float = 1.0


@router.post("/v2g/dispatch")
def v2g_dispatch(payload: V2GDispatchRequest) -> dict:
    vehicles = [V2GVehicle(**v.model_dump()) for v in payload.vehicles]
    allocations = dispatch_v2g(vehicles, payload.feeder_deficit_kw, payload.duration_hours)
    return {
        "allocations": [a.__dict__ for a in allocations],
        "total_dispatched_kw": round(sum(a.discharge_kw for a in allocations), 2),
    }


class BlackoutPlanRequest(BaseModel):
    critical_load: CriticalLoad
    vehicles: list[V2GVehicleIn]
    vehicle_positions: dict[str, tuple[float, float]]
    max_radius_km: float = 3.0
    duration_hours: float = 2.0


@router.post("/blackout/plan")
def blackout_plan(payload: BlackoutPlanRequest) -> dict:
    vehicles = [V2GVehicle(**v.model_dump()) for v in payload.vehicles]
    plan = plan_emergency_backup(
        payload.critical_load, vehicles, payload.vehicle_positions,
        payload.max_radius_km, payload.duration_hours,
    )
    return {
        "critical_load_id": plan.critical_load_id,
        "allocations": [a.__dict__ for a in plan.allocations],
        "total_available_kw": plan.total_available_kw,
        "coverage_ratio": plan.coverage_ratio,
    }


class SolarSyncRequest(BaseModel):
    current_hour: int
    session_duration_hours: int
    station_has_solar: bool
    peak_generation_kw: float
    load_kw: float


@router.post("/solar-sync/recommend")
def solar_sync_recommend(payload: SolarSyncRequest) -> dict:
    return recommend_charging_window(
        payload.current_hour, payload.session_duration_hours, payload.station_has_solar,
        payload.peak_generation_kw, payload.load_kw,
    )


class RecommendationRequest(BaseModel):
    vehicle: Vehicle
    candidates: list[Candidate]
    user_lat: float
    user_lon: float
    hour_of_day: int | None = None
    is_solo_traveler: bool = False


@router.post("/recommendations")
def get_recommendations(payload: RecommendationRequest) -> list[dict]:
    ranked = rank_candidates(
        payload.vehicle, payload.candidates, payload.user_lat, payload.user_lon,
        now=datetime.now(timezone.utc), hour_of_day=payload.hour_of_day, is_solo_traveler=payload.is_solo_traveler,
    )
    return [
        {"candidate_id": r.candidate.id, "distance_km": round(r.distance_km, 3),
         "staleness_hours": round(r.staleness_hours, 2), "score": round(r.score, 3)}
        for r in ranked
    ]


class EmergencyQueueRequest(BaseModel):
    queue_key: str  # e.g. a charger or swap-slot id
    request_id: str
    vehicle_id: str
    is_emergency: bool


@router.post("/emergency-queue/insert")
def emergency_queue_insert(payload: EmergencyQueueRequest) -> dict:
    tracker = _priority_jump_trackers.setdefault(payload.queue_key, PriorityJumpTracker())
    now = datetime.now(timezone.utc)
    new_request = QueuedRequest(payload.request_id, payload.vehicle_id, payload.is_emergency, now)
    updated = insert_with_priority([], new_request, tracker, now)
    jumped = payload.is_emergency and updated[0].id == payload.request_id
    return {"queue_key": payload.queue_key, "jumped_queue": jumped}


class StressTestRequest(BaseModel):
    feeder_id: str
    feeder_capacity_kw: float
    baseline_vehicle_count: int
    avg_charger_power_kw: float
    simultaneous_charge_fraction: float
    density_multipliers: list[float]
    station_capacity_kw: float = 100.0


@router.post("/stress-test/sweep")
def stress_test_sweep(payload: StressTestRequest) -> dict:
    report = sweep_density(
        payload.feeder_id, payload.feeder_capacity_kw, payload.baseline_vehicle_count,
        payload.avg_charger_power_kw, payload.simultaneous_charge_fraction, payload.density_multipliers,
    )
    additional_stations = recommend_additional_stations(report.additional_capacity_needed_kw, payload.station_capacity_kw)
    return {
        "feeder_id": report.feeder_id,
        "results": [r.__dict__ for r in report.results],
        "breaking_point_multiplier": report.breaking_point_multiplier,
        "additional_capacity_needed_kw": report.additional_capacity_needed_kw,
        "recommended_additional_stations": additional_stations,
    }


class WhatIfAllEvRequest(BaseModel):
    scenario: str  # "city" | "corridor" - matches simulation/traci_bridge.py's --scenario
    feeder_id: str
    feeder_capacity_kw: float
    avg_charger_power_kw: float
    simultaneous_charge_fraction: float
    station_capacity_kw: float = 100.0
    current_adoption_rate: float = 0.02


@router.post("/what-if/all-ev")
async def what_if_all_ev_endpoint(payload: WhatIfAllEvRequest) -> dict:
    """Pulls the real current EV count for a scenario from the live twin
    (not a static estimate) and reports the real additional-capacity
    number if every vehicle that count implies were charging, per
    Section 4.6."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.twin_engine_http_url}/state/ev")
    all_ev_state = response.json() if response.status_code == 200 else {}
    current_ev_count = sum(
        1 for v in all_ev_state.values() if v.get("scenario") == payload.scenario
    )
    return what_if_all_ev(
        feeder_id=payload.feeder_id,
        feeder_capacity_kw=payload.feeder_capacity_kw,
        current_ev_vehicle_count=current_ev_count,
        avg_charger_power_kw=payload.avg_charger_power_kw,
        simultaneous_charge_fraction=payload.simultaneous_charge_fraction,
        station_capacity_kw=payload.station_capacity_kw,
        current_adoption_rate=payload.current_adoption_rate,
    )


@router.post("/admin/dpdp-retention-sweep")
def dpdp_retention_sweep(db: Session = Depends(get_db)) -> dict:
    """Admin-triggerable DPDP retention enforcement (Section 4.7) - a real
    deployment would also run this on a schedule (see docs/security-notes.md)."""
    erased_count = run_retention_sweep(db)
    return {"users_erased": erased_count}
