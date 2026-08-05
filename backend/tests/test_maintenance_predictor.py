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


def test_debounced_fault_events_raise_risk_even_with_no_session_history():
    """The fault-detection layer (charger_monitor_sim.py) reports before any
    session history exists for a charger - risk must still reflect it."""
    window = ChargerTelemetryWindow(
        charger_id="c4", total_sessions=0, aborted_sessions=0, error_count=0,
        critical_fault_count=2, warning_fault_count=0,
    )
    assert compute_maintenance_risk_score(window) > 0.5


def test_critical_faults_weigh_more_than_warning_faults():
    critical = compute_maintenance_risk_score(
        ChargerTelemetryWindow("c5", 100, 5, 1, critical_fault_count=1, warning_fault_count=0)
    )
    warning = compute_maintenance_risk_score(
        ChargerTelemetryWindow("c5", 100, 5, 1, critical_fault_count=0, warning_fault_count=1)
    )
    assert critical > warning


def test_fault_signal_adds_on_top_of_healthy_session_history():
    healthy_no_faults = compute_maintenance_risk_score(ChargerTelemetryWindow("c6", 100, 4, 1))
    healthy_with_fault = compute_maintenance_risk_score(
        ChargerTelemetryWindow("c6", 100, 4, 1, critical_fault_count=1)
    )
    assert healthy_with_fault > healthy_no_faults
