from ml.maintenance_predictor import ChargerTelemetryWindow, compute_maintenance_risk_score, is_likely_to_fail_soon


def test_healthy_charger_gets_a_low_risk_score():
    window = ChargerTelemetryWindow(charger_id="c1", total_sessions=100, aborted_sessions=4, error_count=1)
    assert compute_maintenance_risk_score(window) < 0.2
    assert is_likely_to_fail_soon(window) is False


def test_elevated_abort_rate_flags_high_risk():
    window = ChargerTelemetryWindow(charger_id="c2", total_sessions=100, aborted_sessions=40, error_count=2)
    assert compute_maintenance_risk_score(window) >= 0.5
    assert is_likely_to_fail_soon(window) is True


def test_risk_score_increases_monotonically_with_abort_rate():
    low = compute_maintenance_risk_score(ChargerTelemetryWindow("c", 100, 5, 2))
    medium = compute_maintenance_risk_score(ChargerTelemetryWindow("c", 100, 20, 2))
    high = compute_maintenance_risk_score(ChargerTelemetryWindow("c", 100, 50, 2))
    assert low < medium < high


def test_no_sessions_yields_zero_risk_not_a_crash():
    window = ChargerTelemetryWindow(charger_id="c3", total_sessions=0, aborted_sessions=0, error_count=0)
    assert compute_maintenance_risk_score(window) == 0.0
