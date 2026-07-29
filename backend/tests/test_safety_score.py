from datetime import datetime, timezone

from ml.recommendation import Candidate, Vehicle, rank_candidates
from ml.safety_score import compute_safety_score, safety_penalty

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_safety_score_rewards_lighting_and_footfall():
    well_lit_busy = compute_safety_score(lighting_pct=90, footfall_reports_per_week=40, hour_of_day=14)
    dark_empty = compute_safety_score(lighting_pct=10, footfall_reports_per_week=2, hour_of_day=14)
    assert well_lit_busy > dark_empty


def test_safety_score_penalizes_night_hours():
    day_score = compute_safety_score(lighting_pct=50, footfall_reports_per_week=20, hour_of_day=14)
    night_score = compute_safety_score(lighting_pct=50, footfall_reports_per_week=20, hour_of_day=23)
    assert night_score < day_score


def test_safety_penalty_is_inactive_outside_night_solo_context():
    daytime_penalty = safety_penalty(safety_score=0.2, hour_of_day=14, is_solo_traveler=True)
    night_not_solo_penalty = safety_penalty(safety_score=0.2, hour_of_day=23, is_solo_traveler=False)
    assert daytime_penalty == 0.0
    assert night_not_solo_penalty == 0.0


def test_safety_penalty_activates_for_night_plus_solo():
    penalty = safety_penalty(safety_score=0.2, hour_of_day=23, is_solo_traveler=True)
    assert penalty > 0.0


def test_safety_score_flips_the_ranking_for_a_night_solo_traveler():
    """The defining test: a nearer station is poorly lit with low reported
    footfall; a slightly farther station is well-lit and busy. During the
    day, or for a non-solo traveler, distance should still win. At night,
    for a solo traveler, safety must actually change which station wins."""
    vehicle = Vehicle(connector_type="CCS2", is_pluggable=True)
    nearby_unsafe = Candidate(
        id="nearby-unsafe", kind="charge", connector_type="CCS2", lat=12.9355, lon=77.6155,
        predicted_wait_minutes=5, cost_rupees=20, congestion_risk=0.1,
        last_verified_at=NOW, reported_status="available", safety_score=0.1,
    )
    farther_safe = Candidate(
        id="farther-safe", kind="charge", connector_type="CCS2", lat=12.960, lon=77.640,
        predicted_wait_minutes=5, cost_rupees=20, congestion_risk=0.1,
        last_verified_at=NOW, reported_status="available", safety_score=0.95,
    )
    candidates = [nearby_unsafe, farther_safe]
    user_lat, user_lon = 12.9350, 77.6150

    daytime_ranked = rank_candidates(vehicle, candidates, user_lat, user_lon, now=NOW,
                                      hour_of_day=14, is_solo_traveler=True)
    assert daytime_ranked[0].candidate.id == "nearby-unsafe"

    night_group_ranked = rank_candidates(vehicle, candidates, user_lat, user_lon, now=NOW,
                                          hour_of_day=23, is_solo_traveler=False)
    assert night_group_ranked[0].candidate.id == "nearby-unsafe"

    night_solo_ranked = rank_candidates(vehicle, candidates, user_lat, user_lon, now=NOW,
                                         hour_of_day=23, is_solo_traveler=True)
    assert night_solo_ranked[0].candidate.id == "farther-safe"
