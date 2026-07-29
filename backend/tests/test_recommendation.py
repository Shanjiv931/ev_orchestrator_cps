from datetime import datetime, timedelta, timezone

from ml.recommendation import Candidate, Vehicle, is_compatible, rank_by_distance_only, rank_candidates

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
USER_LAT, USER_LON = 12.9350, 77.6150


def test_incompatible_connector_never_enters_ranked_set():
    vehicle = Vehicle(connector_type="CCS2", is_pluggable=True)
    incompatible = Candidate(
        id="c1", kind="charge", connector_type="Bharat AC-001", lat=12.936, lon=77.616,
        predicted_wait_minutes=0, cost_rupees=10, congestion_risk=0.0,
        last_verified_at=NOW, reported_status="available",
    )
    ranked = rank_candidates(vehicle, [incompatible], USER_LAT, USER_LON, now=NOW)
    assert ranked == []


def test_non_pluggable_vehicle_excluded_from_all_charging_recommendations():
    vehicle = Vehicle(connector_type="CCS2", is_pluggable=False)
    charger = Candidate(
        id="c1", kind="charge", connector_type="CCS2", lat=12.936, lon=77.616,
        predicted_wait_minutes=0, cost_rupees=10, congestion_risk=0.0,
        last_verified_at=NOW, reported_status="available",
    )
    assert is_compatible(vehicle, charger) is False
    assert rank_candidates(vehicle, [charger], USER_LAT, USER_LON, now=NOW) == []


def test_swap_only_matches_swap_cassette_vehicles():
    vehicle = Vehicle(connector_type="swap-cassette", is_pluggable=True)
    swap_point = Candidate(
        id="s1", kind="swap", connector_type="swap-cassette", lat=12.936, lon=77.616,
        predicted_wait_minutes=2, cost_rupees=50, congestion_risk=0.1,
        last_verified_at=NOW, reported_status="available",
    )
    charger = Candidate(
        id="c1", kind="charge", connector_type="CCS2", lat=12.936, lon=77.616,
        predicted_wait_minutes=0, cost_rupees=10, congestion_risk=0.0,
        last_verified_at=NOW, reported_status="available",
    )
    ranked = rank_candidates(vehicle, [swap_point, charger], USER_LAT, USER_LON, now=NOW)
    assert len(ranked) == 1
    assert ranked[0].candidate.id == "s1"


def test_offline_station_is_excluded():
    vehicle = Vehicle(connector_type="CCS2", is_pluggable=True)
    offline = Candidate(
        id="c1", kind="charge", connector_type="CCS2", lat=12.936, lon=77.616,
        predicted_wait_minutes=0, cost_rupees=10, congestion_risk=0.0,
        last_verified_at=NOW, reported_status="offline",
    )
    assert rank_candidates(vehicle, [offline], USER_LAT, USER_LON, now=NOW) == []


def test_trust_aware_scorer_beats_naive_distance_only_baseline():
    """The defining test: a nearer station claims 'available' but hasn't
    been genuinely verified in 30 hours (stale - likely non-functional per
    the real ~25-48% failure rate this platform targets). A farther station
    is fresh, low-wait, and low-congestion. The naive distance-only baseline
    (what existing apps do) picks the bad nearby station; our scorer must
    pick the good farther one instead."""
    vehicle = Vehicle(connector_type="CCS2", is_pluggable=True)
    nearby_but_stale = Candidate(
        id="nearby-stale", kind="charge", connector_type="CCS2", lat=12.9355, lon=77.6155,
        predicted_wait_minutes=25, cost_rupees=20, congestion_risk=0.6,
        last_verified_at=NOW - timedelta(hours=30), reported_status="available",
    )
    farther_but_trustworthy = Candidate(
        id="far-fresh", kind="charge", connector_type="CCS2", lat=12.960, lon=77.640,
        predicted_wait_minutes=2, cost_rupees=18, congestion_risk=0.05,
        last_verified_at=NOW - timedelta(minutes=5), reported_status="available",
    )
    candidates = [nearby_but_stale, farther_but_trustworthy]

    naive_top = rank_by_distance_only(vehicle, candidates, USER_LAT, USER_LON)[0]
    assert naive_top.id == "nearby-stale"  # confirms the baseline really is naive

    smart_ranked = rank_candidates(vehicle, candidates, USER_LAT, USER_LON, now=NOW)
    assert smart_ranked[0].candidate.id == "far-fresh"


def test_fresher_verification_scores_better_than_stale_at_equal_distance():
    vehicle = Vehicle(connector_type="CCS2", is_pluggable=True)
    fresh = Candidate(
        id="fresh", kind="charge", connector_type="CCS2", lat=12.936, lon=77.616,
        predicted_wait_minutes=5, cost_rupees=20, congestion_risk=0.2,
        last_verified_at=NOW - timedelta(minutes=10), reported_status="available",
    )
    stale = Candidate(
        id="stale", kind="charge", connector_type="CCS2", lat=12.936, lon=77.616,
        predicted_wait_minutes=5, cost_rupees=20, congestion_risk=0.2,
        last_verified_at=NOW - timedelta(hours=40), reported_status="available",
    )
    ranked = rank_candidates(vehicle, [stale, fresh], USER_LAT, USER_LON, now=NOW)
    assert ranked[0].candidate.id == "fresh"
