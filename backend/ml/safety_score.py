"""Safety score for stations/swap points (Section 5.4).

A composite of lighting, reported footfall, and time-of-day risk, that
must actually change the recommendation ranking output for night-time and
solo-traveler contexts - not sit unused as a display-only number.
"""
from __future__ import annotations

NIGHT_START_HOUR = 20
NIGHT_END_HOUR = 5

# How heavily safety factors into the composite recommendation score when
# the context calls for it. 0 in normal daytime contexts (safety score is
# still computed and shown, just doesn't override distance/cost/wait).
SAFETY_WEIGHT_NIGHT_SOLO = 8.0
SAFETY_WEIGHT_DEFAULT = 0.0


def is_night_hour(hour_of_day: int) -> bool:
    return hour_of_day >= NIGHT_START_HOUR or hour_of_day < NIGHT_END_HOUR


def compute_safety_score(lighting_pct: float, footfall_reports_per_week: float, hour_of_day: int) -> float:
    """Returns a score in [0, 1] - higher is safer."""
    lighting_component = max(0.0, min(1.0, lighting_pct / 100.0))
    footfall_component = max(0.0, min(1.0, footfall_reports_per_week / 50.0))
    time_risk_penalty = 0.3 if is_night_hour(hour_of_day) else 0.0
    score = 0.5 * lighting_component + 0.5 * footfall_component - time_risk_penalty
    return max(0.0, min(1.0, score))


def safety_penalty(safety_score: float, hour_of_day: int, is_solo_traveler: bool) -> float:
    """A score-space penalty (higher = worse) to add into a composite
    recommendation score, following the same "lower is better" convention
    as ml.recommendation. Only meaningfully active in a night + solo
    context; otherwise contributes ~0 so it doesn't override other factors
    when there's no real safety concern to weigh."""
    weight = SAFETY_WEIGHT_NIGHT_SOLO if (is_night_hour(hour_of_day) and is_solo_traveler) else SAFETY_WEIGHT_DEFAULT
    return weight * (1.0 - safety_score)
