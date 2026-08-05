from ml.rural_minigrid import estimate_safe_ev_capacity, validate_recommendation_respects_minigrid_headroom


def test_rural_minigrid_supports_far_fewer_simultaneous_evs_than_an_urban_feeder():
    rural = estimate_safe_ev_capacity(feeder_capacity_kw=25.0)  # matches simulation's Anaicut feeder
    urban = estimate_safe_ev_capacity(feeder_capacity_kw=1000.0)  # matches simulation's VIT DC hub feeder
    assert rural.max_safe_vehicle_count < urban.max_safe_vehicle_count


def test_capacity_scales_with_feeder_size_at_fixed_charger_power():
    small = estimate_safe_ev_capacity(feeder_capacity_kw=25.0, charger_power_kw=3.3)
    large = estimate_safe_ev_capacity(feeder_capacity_kw=50.0, charger_power_kw=3.3)
    assert large.max_safe_vehicle_count >= small.max_safe_vehicle_count


def test_safety_margin_prevents_recommending_a_capacity_that_uses_the_entire_feeder():
    report = estimate_safe_ev_capacity(feeder_capacity_kw=10.0, charger_power_kw=3.3, safety_margin=0.9)
    total_recommended_load = report.max_safe_vehicle_count * report.charger_power_kw
    assert total_recommended_load <= 10.0 * 0.9 + 1e-9


def test_recommendation_headroom_check_rejects_overloading_a_rural_feeder():
    assert validate_recommendation_respects_minigrid_headroom(
        feeder_current_load_kw=20.0, feeder_capacity_kw=25.0, additional_charger_power_kw=3.3,
    ) is True
    assert validate_recommendation_respects_minigrid_headroom(
        feeder_current_load_kw=23.0, feeder_capacity_kw=25.0, additional_charger_power_kw=3.3,
    ) is False


def test_zero_capacity_feeder_supports_no_vehicles():
    report = estimate_safe_ev_capacity(feeder_capacity_kw=0.0)
    assert report.max_safe_vehicle_count == 0
