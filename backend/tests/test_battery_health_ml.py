import uuid
from datetime import datetime, timedelta, timezone

from app.models import BatteryHealth, User, Vehicle
from ml.battery_health import (
    blended_slope,
    detect_trend_anomaly,
    estimate_soh_pct,
    individual_degradation_slope,
    population_degradation_slope,
    project_months_to_threshold,
)


def test_estimate_soh_is_monotonic_in_each_stressor():
    baseline = estimate_soh_pct(cycle_count=100, avg_soc_held_pct=50, fast_charge_frequency=0.1, avg_temp_exposure_c=25)
    more_cycles = estimate_soh_pct(cycle_count=500, avg_soc_held_pct=50, fast_charge_frequency=0.1, avg_temp_exposure_c=25)
    more_fast_charging = estimate_soh_pct(cycle_count=100, avg_soc_held_pct=50, fast_charge_frequency=0.8, avg_temp_exposure_c=25)
    hotter = estimate_soh_pct(cycle_count=100, avg_soc_held_pct=50, fast_charge_frequency=0.1, avg_temp_exposure_c=45)
    higher_soc_held = estimate_soh_pct(cycle_count=100, avg_soc_held_pct=95, fast_charge_frequency=0.1, avg_temp_exposure_c=25)

    assert more_cycles < baseline
    assert more_fast_charging < baseline
    assert hotter < baseline
    assert higher_soc_held < baseline


def _make_user(db_session) -> User:
    user = User(name="Test", email=f"{uuid.uuid4().hex}@example.com", hashed_password="x", persona="individual_driver")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_vehicle(db_session, user: User, chemistry: str = "NMC", vehicle_class: str = "4W") -> Vehicle:
    vehicle = Vehicle(user_id=user.id, vehicle_class=vehicle_class, connector_type="CCS2",
                       battery_chemistry=chemistry, is_pluggable=True)
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)
    return vehicle


def _add_health_record(db_session, vehicle: Vehicle, soh_pct: float, months_ago: float) -> None:
    recorded_at = datetime.now(timezone.utc) - timedelta(days=months_ago * 30)
    db_session.add(BatteryHealth(vehicle_id=vehicle.id, soh_pct=soh_pct, recorded_at=recorded_at))
    db_session.commit()


def test_population_query_sharpens_rul_estimate_beyond_individual_only(db_session):
    """The Section 11 acceptance criterion, directly: a new vehicle's own
    history is thin and noisy; cross-referencing peer twins of the same
    chemistry/class must measurably improve the RUL projection versus using
    that vehicle's own history alone."""
    user = _make_user(db_session)

    true_population_slope = -0.5  # %/month, consistent across peers
    for _ in range(5):
        peer = _make_vehicle(db_session, user)
        _add_health_record(db_session, peer, soh_pct=95.0, months_ago=6)
        _add_health_record(db_session, peer, soh_pct=95.0 + true_population_slope * 3, months_ago=3)
        _add_health_record(db_session, peer, soh_pct=95.0 + true_population_slope * 6, months_ago=0)

    target = _make_vehicle(db_session, user)
    _add_health_record(db_session, target, soh_pct=95.0, months_ago=1)
    _add_health_record(db_session, target, soh_pct=90.0, months_ago=0)  # noisy: implies -5.0%/month

    individual = individual_degradation_slope(
        db_session.query(BatteryHealth).filter(BatteryHealth.vehicle_id == target.id).all()
    )
    population = population_degradation_slope(db_session, "NMC", "4W", exclude_vehicle_id=target.id)
    blended = blended_slope(individual, population)

    assert individual.slope_pct_per_month < -4.0  # confirms the individual estimate really is noisy/wrong
    assert population.sample_count == 5
    assert abs(population.slope_pct_per_month - true_population_slope) < 0.1

    current_soh = 90.0
    true_months = (current_soh - 80.0) / abs(true_population_slope)
    individual_only_months = project_months_to_threshold(current_soh, individual.slope_pct_per_month)
    blended_months = project_months_to_threshold(current_soh, blended)

    assert abs(blended_months - true_months) < abs(individual_only_months - true_months)


def test_population_slope_ignores_vehicles_of_a_different_chemistry(db_session):
    user = _make_user(db_session)
    lfp_peer = _make_vehicle(db_session, user, chemistry="LFP")
    _add_health_record(db_session, lfp_peer, soh_pct=95.0, months_ago=3)
    _add_health_record(db_session, lfp_peer, soh_pct=80.0, months_ago=0)  # steep unrelated decline

    target = _make_vehicle(db_session, user, chemistry="NMC")
    population = population_degradation_slope(db_session, "NMC", "4W", exclude_vehicle_id=target.id)
    assert population.sample_count == 0


def test_project_months_returns_none_when_not_degrading():
    assert project_months_to_threshold(current_soh_pct=95.0, slope_pct_per_month=0.0) is None
    assert project_months_to_threshold(current_soh_pct=95.0, slope_pct_per_month=0.2) is None


def test_project_months_zero_when_already_at_or_below_threshold():
    assert project_months_to_threshold(current_soh_pct=78.0, slope_pct_per_month=-0.5) == 0.0


def test_trend_anomaly_flags_acceleration_relative_to_own_history():
    assert detect_trend_anomaly(recent_slope_pct_per_month=-1.5, historical_slope_pct_per_month=-0.5) == "accelerating"
    assert detect_trend_anomaly(recent_slope_pct_per_month=-0.5, historical_slope_pct_per_month=-0.5) == "stable"
    assert detect_trend_anomaly(recent_slope_pct_per_month=-0.1, historical_slope_pct_per_month=-0.5) == "improving"
