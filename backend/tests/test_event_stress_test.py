from ml.event_stress_test import recommend_additional_stations, sweep_density


def test_low_density_stays_within_capacity():
    report = sweep_density(
        feeder_id="feeder-x", feeder_capacity_kw=200.0, baseline_vehicle_count=10,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5, density_multipliers=[1.0],
    )
    assert report.results[0].is_overloaded is False
    assert report.breaking_point_multiplier is None


def test_report_identifies_the_breaking_point_density():
    """Section 5.6's core requirement: report exactly which density level
    causes the feeder to fail."""
    report = sweep_density(
        feeder_id="feeder-koramangala", feeder_capacity_kw=100.0, baseline_vehicle_count=20,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5,
        density_multipliers=[1.0, 2.0, 3.0, 4.0, 5.0],
    )
    assert report.breaking_point_multiplier is not None
    # confirm every level at or above the breaking point is flagged overloaded
    for r in report.results:
        if r.density_multiplier >= report.breaking_point_multiplier:
            assert r.is_overloaded is True
        else:
            assert r.is_overloaded is False


def test_additional_capacity_recommendation_scales_with_overload_severity():
    small_overload = sweep_density(
        feeder_id="f1", feeder_capacity_kw=100.0, baseline_vehicle_count=20,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5, density_multipliers=[1.5],
    )
    large_overload = sweep_density(
        feeder_id="f1", feeder_capacity_kw=100.0, baseline_vehicle_count=20,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5, density_multipliers=[5.0],
    )
    assert large_overload.additional_capacity_needed_kw > small_overload.additional_capacity_needed_kw


def test_recommend_additional_stations_rounds_up_to_cover_the_deficit():
    assert recommend_additional_stations(additional_capacity_needed_kw=250.0, station_capacity_kw=100.0) == 3
    assert recommend_additional_stations(additional_capacity_needed_kw=0.0, station_capacity_kw=100.0) == 0
    assert recommend_additional_stations(additional_capacity_needed_kw=100.0, station_capacity_kw=100.0) == 1
