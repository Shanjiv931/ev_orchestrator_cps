import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from charger_monitor_sim import ChargerMonitorState, FaultInjectionRate, evaluate


def _reading(**overrides):
    base = {
        "charger_id": "station-x-charger-0", "station_id": "station-x", "station_type": "public_dc_hub",
        "status": "occupied", "rated_power_kw": 60.0, "voltage_v": 400.0, "current_a": 150.0,
        "temperature_c": 45.0,
    }
    base.update(overrides)
    return base


def test_normal_reading_produces_no_immediate_fault():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()  # baseline - injection is rare but not impossible; force it off for determinism
    rate._rate_key = "off"
    result = evaluate(state, _reading(), rate)
    assert result is None or result[0] == "NoError"


def test_overcurrent_is_debounced_before_reporting():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()
    rate._rate_key = "off"
    # Rated current for 60kW @ 400V ~= 153A, so 300A is a genuine overload.
    reading = _reading(current_a=300.0)
    first = evaluate(state, reading, rate)
    # First call on a fresh state also clears the "never reported" heartbeat
    # (last_report_at starts at 0.0) - the breach itself only starts the
    # debounce streak, it doesn't report on its own yet.
    assert first is None or first == ("NoError", "info")
    second = evaluate(state, reading, rate)
    assert second == ("OverCurrentFailure", "critical")


def test_overvoltage_detected_past_tolerance():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()
    rate._rate_key = "off"
    reading = _reading(voltage_v=470.0)  # >10% over 400V nominal
    evaluate(state, reading, rate)
    result = evaluate(state, reading, rate)
    assert result == ("OverVoltage", "critical")


def test_high_temperature_detected_for_dc_charger():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()
    rate._rate_key = "off"
    reading = _reading(temperature_c=85.0)  # > 70C DC limit
    evaluate(state, reading, rate)
    result = evaluate(state, reading, rate)
    assert result == ("HighTemperature", "critical")


def test_zero_current_while_occupied_reports_power_meter_failure():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()
    rate._rate_key = "off"
    reading = _reading(current_a=0.0)
    result = None
    for _ in range(4):
        result = evaluate(state, reading, rate)
    assert result == ("PowerMeterFailure", "critical")


def test_available_charger_with_zero_current_is_healthy():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()
    rate._rate_key = "off"
    reading = _reading(status="available", current_a=0.05)
    for _ in range(4):
        result = evaluate(state, reading, rate)
    assert result is None or result[0] == "NoError"


def test_highway_corridor_station_gets_weaker_signal_baseline():
    state = ChargerMonitorState()
    rate = FaultInjectionRate()
    rate._rate_key = "off"
    evaluate(state, _reading(station_type="highway_corridor"), rate)
    assert state.signal_baseline_pct == 65.0
    evaluate(state, _reading(station_type="public_dc_hub"), rate)
    assert state.signal_baseline_pct == 90.0
