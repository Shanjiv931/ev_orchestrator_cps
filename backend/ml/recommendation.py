"""Recommendation / charge-vs-swap scorer (Section 4.5.2).

Ranks compatible stations and swap points by distance, predicted wait,
cost, and congestion risk - AFTER the connector/chemistry compatibility
filter and the reported-vs-verified trust-layer penalty from Section 4.2.
An incompatible station must never enter the ranked candidate set, and a
station with fresh-looking status but stale verification must be penalized,
not trusted at face value.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

CHARGE_CONNECTORS = {"Bharat AC-001", "Bharat DC-001", "CCS2", "Type 2"}
SWAP_CONNECTOR = "swap-cassette"

# Weights for the composite score - lower is better. Tuned so that a
# moderately-farther station with materially better real availability beats
# a nearer station whose "available" status is not to be trusted.
_WEIGHT_DISTANCE_KM = 1.0
_WEIGHT_WAIT_MIN = 0.5
_WEIGHT_COST_RUPEES = 0.1
_WEIGHT_CONGESTION = 5.0
_STALENESS_PENALTY_PER_HOUR = 3.0


@dataclass
class Vehicle:
    connector_type: str
    is_pluggable: bool


@dataclass
class Candidate:
    id: str
    kind: str  # "charge" | "swap"
    connector_type: str
    lat: float
    lon: float
    predicted_wait_minutes: float
    cost_rupees: float
    congestion_risk: float  # 0.0 (empty) - 1.0 (saturated)
    last_verified_at: datetime | None
    reported_status: str  # "available" | "occupied" | "offline"


@dataclass
class RankedCandidate:
    candidate: Candidate
    distance_km: float
    staleness_hours: float
    score: float


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_compatible(vehicle: Vehicle, candidate: Candidate) -> bool:
    """Connector/chemistry compatibility filter - runs before ranking, per
    Section 4.2, so an incompatible station never enters the candidate set."""
    if candidate.kind == "swap":
        return vehicle.connector_type == SWAP_CONNECTOR
    if not vehicle.is_pluggable:
        return False  # non-plug-in hybrids are excluded from charging recs, not mismatched
    return vehicle.connector_type == candidate.connector_type


def _staleness_hours(candidate: Candidate, now: datetime) -> float:
    if candidate.last_verified_at is None:
        return 999.0  # never verified - treat as maximally stale
    delta = now - candidate.last_verified_at
    return max(0.0, delta.total_seconds() / 3600.0)


def score_candidate(vehicle: Vehicle, candidate: Candidate, user_lat: float, user_lon: float,
                     now: datetime | None = None) -> RankedCandidate | None:
    if not is_compatible(vehicle, candidate):
        return None
    now = now or datetime.now(timezone.utc)
    if candidate.reported_status == "offline":
        return None

    distance_km = _haversine_km(user_lat, user_lon, candidate.lat, candidate.lon)
    staleness_hours = _staleness_hours(candidate, now)
    trust_penalty = staleness_hours * _STALENESS_PENALTY_PER_HOUR

    score = (
        distance_km * _WEIGHT_DISTANCE_KM
        + candidate.predicted_wait_minutes * _WEIGHT_WAIT_MIN
        + candidate.cost_rupees * _WEIGHT_COST_RUPEES
        + candidate.congestion_risk * _WEIGHT_CONGESTION
        + trust_penalty
    )
    return RankedCandidate(candidate=candidate, distance_km=distance_km, staleness_hours=staleness_hours, score=score)


def rank_candidates(vehicle: Vehicle, candidates: list[Candidate], user_lat: float, user_lon: float,
                     now: datetime | None = None) -> list[RankedCandidate]:
    scored = [score_candidate(vehicle, c, user_lat, user_lon, now) for c in candidates]
    ranked = [s for s in scored if s is not None]
    ranked.sort(key=lambda r: r.score)
    return ranked


def rank_by_distance_only(vehicle: Vehicle, candidates: list[Candidate], user_lat: float, user_lon: float) -> list[Candidate]:
    """Naive baseline: filters for compatibility (a real app would at least
    do this) but ranks purely by distance, ignoring wait/cost/congestion/
    trust entirely - what most existing charging apps effectively do today."""
    compatible = [c for c in candidates if is_compatible(vehicle, c) and c.reported_status != "offline"]
    compatible.sort(key=lambda c: _haversine_km(user_lat, user_lon, c.lat, c.lon))
    return compatible
