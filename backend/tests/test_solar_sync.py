from ml.solar_sync import recommend_charging_window, solar_generation_kw_at


def test_no_generation_outside_daylight_hours():
    assert solar_generation_kw_at(3.0, peak_generation_kw=10.0) == 0.0
    assert solar_generation_kw_at(21.0, peak_generation_kw=10.0) == 0.0


def test_non_solar_station_picks_the_cheapest_tariff_hour():
    result = recommend_charging_window(
        current_hour=10, session_duration_hours=2, station_has_solar=False, peak_generation_kw=0.0, load_kw=7.0,
    )
    assert result["recommended_start_hour"] == 0  # off-peak window in the default tariff


def test_solar_station_skews_toward_midday_despite_costlier_daytime_tariff():
    result = recommend_charging_window(
        current_hour=10, session_duration_hours=2, station_has_solar=True, peak_generation_kw=7.0, load_kw=7.0,
    )
    assert 9 <= result["recommended_start_hour"] <= 15


def test_solar_recommendation_costs_less_than_non_solar_at_the_same_station_shape():
    solar_result = recommend_charging_window(
        current_hour=10, session_duration_hours=2, station_has_solar=True, peak_generation_kw=7.0, load_kw=7.0,
    )
    non_solar_result = recommend_charging_window(
        current_hour=10, session_duration_hours=2, station_has_solar=False, peak_generation_kw=0.0, load_kw=7.0,
    )
    assert solar_result["estimated_cost_per_kwh_total"] < non_solar_result["estimated_cost_per_kwh_total"]


def test_larger_solar_array_relative_to_load_reduces_cost_further():
    small_array = recommend_charging_window(
        current_hour=11, session_duration_hours=1, station_has_solar=True, peak_generation_kw=2.0, load_kw=7.0,
    )
    large_array = recommend_charging_window(
        current_hour=11, session_duration_hours=1, station_has_solar=True, peak_generation_kw=20.0, load_kw=7.0,
    )
    assert large_array["estimated_cost_per_kwh_total"] <= small_array["estimated_cost_per_kwh_total"]
