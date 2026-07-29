"""Rural mini-grid mode (Section 5.12).

An isolated village-scale solar micro-grid feeder has a hard, low capacity
ceiling, structurally different from an urban DISCOM feeder - not just a
smaller number, but a regime where a handful of simultaneous fast chargers
can plausibly saturate the entire local supply. This module provides the
capacity-planning check specific to that scale: how many EVs (predominantly
2W/3W, the vehicle classes actually driving India's next EV adoption wave
in rural areas) a given mini-grid can safely support charging at once.
"""
from __future__ import annotations

from dataclasses import dataclass

# Typical rural 2W/3W AC charging draw is far below urban DC fast-charging
# power - this module models that reality rather than assuming DC hub-scale
# chargers exist in a village setting.
TYPICAL_RURAL_CHARGER_POWER_KW = 3.3


@dataclass
class MiniGridCapacityReport:
    feeder_capacity_kw: float
    charger_power_kw: float
    simultaneous_charge_fraction: float
    max_safe_vehicle_count: int


def estimate_safe_ev_capacity(feeder_capacity_kw: float, charger_power_kw: float = TYPICAL_RURAL_CHARGER_POWER_KW,
                               simultaneous_charge_fraction: float = 1.0,
                               safety_margin: float = 0.9) -> MiniGridCapacityReport:
    """simultaneous_charge_fraction models what share of connected
    chargers are realistically drawing power at once; for a rural
    mini-grid worst-case planning, default to 1.0 (assume all could draw
    simultaneously, since there's no diversity data to rely on yet)."""
    usable_capacity_kw = feeder_capacity_kw * safety_margin
    effective_power_per_vehicle = charger_power_kw * simultaneous_charge_fraction
    max_count = int(usable_capacity_kw // effective_power_per_vehicle) if effective_power_per_vehicle > 0 else 0
    return MiniGridCapacityReport(
        feeder_capacity_kw=feeder_capacity_kw,
        charger_power_kw=charger_power_kw,
        simultaneous_charge_fraction=simultaneous_charge_fraction,
        max_safe_vehicle_count=max(0, max_count),
    )


def validate_recommendation_respects_minigrid_headroom(feeder_current_load_kw: float, feeder_capacity_kw: float,
                                                          additional_charger_power_kw: float) -> bool:
    """The specific 'does the recommendation/grid-protection logic still
    behave sensibly at rural scale' check: adding one more charging
    recommendation must never be approved if it would push a rural
    mini-grid over capacity - the same congestion_risk factor
    recommendation.py already uses, but checked explicitly against a hard
    ceiling here, since a mini-grid has no slack for "soft" overshoot the
    way a large urban feeder does."""
    return (feeder_current_load_kw + additional_charger_power_kw) <= feeder_capacity_kw
