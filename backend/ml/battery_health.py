"""Battery Health & Replacement Advisory (Section 4.5.4).

Estimates State-of-Health (SoH) from simulated usage stressors, always kept
separate from State-of-Charge (SoC) - `soh_pct` never appears alongside a
merged SoC value anywhere in this module's return types. Projects months
remaining to the 80%-capacity replacement threshold, flags trend anomalies,
and - the differentiating piece - sharpens that projection with an actual
population query against other vehicle twins of the same chemistry/usage
profile, not a comment describing the idea.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BatteryHealth, Vehicle

REPLACEMENT_THRESHOLD_PCT = 80.0
SHRINKAGE_PRIOR_STRENGTH = 4.0  # higher = population prior dominates until more of the vehicle's own data accrues
ANOMALY_ACCELERATION_RATIO = 1.5


def estimate_soh_pct(cycle_count: float, avg_soc_held_pct: float, fast_charge_frequency: float,
                      avg_temp_exposure_c: float) -> float:
    """Empirical SoH model driven by four simulated usage stressors.
    Monotonic in each: more cycles, more time spent at high average SoC,
    more frequent fast charging, and hotter average temperature exposure
    all reduce SoH - the well-established real-world degradation drivers.
    """
    cycle_wear = cycle_count * 0.015
    calendar_wear = max(0.0, avg_soc_held_pct - 50.0) * 0.04
    fast_charge_wear = fast_charge_frequency * 3.0
    thermal_wear = max(0.0, avg_temp_exposure_c - 25.0) * 0.06
    soh = 100.0 - cycle_wear - calendar_wear - fast_charge_wear - thermal_wear
    return float(np.clip(soh, 0.0, 100.0))


@dataclass
class DegradationSlope:
    slope_pct_per_month: float
    sample_count: int


def _linear_slope_pct_per_month(soh_by_month: list[tuple[float, float]]) -> DegradationSlope:
    """soh_by_month: list of (months_since_first_record, soh_pct)."""
    if len(soh_by_month) < 2:
        return DegradationSlope(slope_pct_per_month=0.0, sample_count=len(soh_by_month))
    months = np.array([m for m, _ in soh_by_month], dtype=float)
    soh = np.array([s for _, s in soh_by_month], dtype=float)
    slope, _intercept = np.polyfit(months, soh, deg=1)
    return DegradationSlope(slope_pct_per_month=float(slope), sample_count=len(soh_by_month))


def individual_degradation_slope(records: list[BatteryHealth]) -> DegradationSlope:
    if not records:
        return DegradationSlope(slope_pct_per_month=0.0, sample_count=0)
    ordered = sorted(records, key=lambda r: r.recorded_at)
    t0 = ordered[0].recorded_at
    soh_by_month = [((r.recorded_at - t0).days / 30.0, r.soh_pct) for r in ordered]
    return _linear_slope_pct_per_month(soh_by_month)


def population_degradation_slope(db: Session, battery_chemistry: str, vehicle_class: str,
                                  exclude_vehicle_id) -> DegradationSlope:
    """Real population query against the twin store's persisted history:
    pulls every OTHER vehicle sharing this chemistry/usage profile and
    computes their average individual degradation slope. This is what lets
    the platform sharpen a single vehicle's RUL estimate beyond what an
    isolated BMS could ever produce."""
    peer_vehicle_ids = db.scalars(
        select(Vehicle.id)
        .where(Vehicle.battery_chemistry == battery_chemistry)
        .where(Vehicle.vehicle_class == vehicle_class)
        .where(Vehicle.id != exclude_vehicle_id)
    ).all()
    if not peer_vehicle_ids:
        return DegradationSlope(slope_pct_per_month=0.0, sample_count=0)

    slopes = []
    for peer_id in peer_vehicle_ids:
        peer_records = db.scalars(
            select(BatteryHealth).where(BatteryHealth.vehicle_id == peer_id).order_by(BatteryHealth.recorded_at)
        ).all()
        peer_slope = individual_degradation_slope(list(peer_records))
        if peer_slope.sample_count >= 2:
            slopes.append(peer_slope.slope_pct_per_month)

    if not slopes:
        return DegradationSlope(slope_pct_per_month=0.0, sample_count=0)
    return DegradationSlope(slope_pct_per_month=float(np.mean(slopes)), sample_count=len(slopes))


def blended_slope(individual: DegradationSlope, population: DegradationSlope) -> float:
    """Empirical-Bayes shrinkage: weight toward the individual estimate as
    more of the vehicle's own data accumulates, toward the population
    estimate when the vehicle's own history is thin or noisy."""
    if population.sample_count == 0:
        return individual.slope_pct_per_month
    weight_individual = individual.sample_count / (individual.sample_count + SHRINKAGE_PRIOR_STRENGTH)
    return weight_individual * individual.slope_pct_per_month + (1 - weight_individual) * population.slope_pct_per_month


def project_months_to_threshold(current_soh_pct: float, slope_pct_per_month: float) -> float | None:
    if slope_pct_per_month >= 0:
        return None  # not degrading (or improving) - no projected replacement date
    if current_soh_pct <= REPLACEMENT_THRESHOLD_PCT:
        return 0.0
    return (current_soh_pct - REPLACEMENT_THRESHOLD_PCT) / abs(slope_pct_per_month)


def detect_trend_anomaly(recent_slope_pct_per_month: float, historical_slope_pct_per_month: float) -> str:
    """Compares a vehicle's recent degradation rate against its own earlier
    history - not a fixed threshold - so "normal for this chemistry" isn't
    conflated with "normal for this specific vehicle's own past"."""
    if historical_slope_pct_per_month >= -0.01:
        return "stable" if recent_slope_pct_per_month >= -0.01 else "accelerating"
    ratio = recent_slope_pct_per_month / historical_slope_pct_per_month
    if ratio >= ANOMALY_ACCELERATION_RATIO:
        return "accelerating"
    if ratio <= 0.5:
        return "improving"
    return "stable"
