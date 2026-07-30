import pytest

from ml.event_stress_test import what_if_all_ev


def test_all_ev_scenario_extrapolates_far_more_vehicles_than_today():
    result = what_if_all_ev(
        feeder_id="feeder-x", feeder_capacity_kw=200.0, current_ev_vehicle_count=10,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5,
    )
    assert result["today_ev_vehicle_count"] == 10
    assert result["all_ev_vehicle_count"] == 500  # 10 / 0.02


def test_all_ev_scenario_can_report_overload_from_a_small_real_today_count():
    result = what_if_all_ev(
        feeder_id="feeder-koramangala", feeder_capacity_kw=1000.0, current_ev_vehicle_count=40,
        avg_charger_power_kw=60.0, simultaneous_charge_fraction=0.5,
    )
    assert result["all_ev_is_overloaded"] is True
    assert result["additional_stations_needed"] > 0


def test_uses_a_lower_adoption_rate_when_provided():
    default_rate = what_if_all_ev(
        feeder_id="f", feeder_capacity_kw=100.0, current_ev_vehicle_count=10,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5,
    )
    lower_rate = what_if_all_ev(
        feeder_id="f", feeder_capacity_kw=100.0, current_ev_vehicle_count=10,
        avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5, current_adoption_rate=0.01,
    )
    assert lower_rate["all_ev_vehicle_count"] > default_rate["all_ev_vehicle_count"]


def test_rejects_non_positive_adoption_rate():
    with pytest.raises(ValueError):
        what_if_all_ev(
            feeder_id="f", feeder_capacity_kw=100.0, current_ev_vehicle_count=10,
            avg_charger_power_kw=7.0, simultaneous_charge_fraction=0.5, current_adoption_rate=0,
        )
