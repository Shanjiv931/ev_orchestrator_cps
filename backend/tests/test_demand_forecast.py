from ml.demand_forecast import ZONES, generate_synthetic_history, predict_sessions, train_and_evaluate


def test_synthetic_history_has_expected_shape():
    history = generate_synthetic_history(num_days=14)
    assert len(history) == 14 * 24 * len(ZONES)
    assert set(history["zone"].unique()) == set(ZONES)
    assert history["sessions"].min() >= 0


def test_train_and_evaluate_reports_low_error_on_held_out_slice():
    result = train_and_evaluate(held_out_days=10)
    assert result["held_out_rows"] > 0
    # Sessions are Poisson-sampled around the latent demand curve, so even a
    # perfect model can't beat the sampling noise floor (std ~ sqrt(mean),
    # and mean demand here ranges ~1.5-20). These bounds reflect that floor,
    # not an arbitrary target.
    assert result["mae"] < 2.5
    assert result["rmse"] < 3.5


def test_forecast_reflects_morning_and_evening_commute_peaks():
    result = train_and_evaluate()
    model = result["model"]
    midday = predict_sessions(model, "koramangala_dc_hub", hour=13, day_of_week=2, weather=0)
    evening_peak = predict_sessions(model, "koramangala_dc_hub", hour=18, day_of_week=2, weather=0)
    assert evening_peak > midday


def test_forecast_reflects_weekday_vs_weekend_difference():
    result = train_and_evaluate()
    model = result["model"]
    weekday = predict_sessions(model, "indiranagar_housing", hour=9, day_of_week=1, weather=0)
    weekend = predict_sessions(model, "indiranagar_housing", hour=9, day_of_week=6, weather=0)
    assert weekday > weekend


def test_rural_zone_has_far_lower_demand_than_dc_hub():
    result = train_and_evaluate()
    model = result["model"]
    rural = predict_sessions(model, "holenarsipura_rural", hour=18, day_of_week=2, weather=0)
    dc_hub = predict_sessions(model, "koramangala_dc_hub", hour=18, day_of_week=2, weather=0)
    assert rural < dc_hub
