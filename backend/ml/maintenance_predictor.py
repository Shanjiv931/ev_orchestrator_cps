"""Predictive charger/swap-point maintenance (Section 5.11).

Lightweight anomaly detection on simulated charger telemetry - unusual
error rates or session-abort frequency, now joined by real OCPP fault
codes from the embedded fault-detection layer
(simulation/charger_monitor_sim.py, consumed by
app/services/fault_consumer.py) - flagging a station as "likely to fail
soon" before it goes fully offline. Feeds directly into the trust layer
(Section 4.2) via the existing `Charger.maintenance_risk_score` column
(Phase 4 schema) rather than existing as a separate silo, exactly as
docs/security-notes.md already anticipated a richer fault signal would.
"""
from __future__ import annotations

from dataclasses import dataclass

# A well-behaved charger aborts roughly this fraction of sessions in normal
# operation (connector faults, driver cancellations, etc.) - only material
# excess above this baseline signals a real problem.
BASELINE_ABORT_RATE = 0.05
BASELINE_ERROR_RATE = 0.02

# A single debounced critical OCPP fault (OverCurrentFailure, GroundFailure,
# etc.) is treated as roughly as significant as running at ~1.5x the
# baseline abort rate; a warning-severity fault (ReaderFailure, WeakSignal)
# about half that - these are independent evidence on top of the
# session-level abort/error signal, not a replacement for it.
CRITICAL_FAULT_WEIGHT = 0.8
WARNING_FAULT_WEIGHT = 0.3


@dataclass
class ChargerTelemetryWindow:
    charger_id: str
    total_sessions: int
    aborted_sessions: int
    error_count: int
    critical_fault_count: int = 0
    warning_fault_count: int = 0


def compute_maintenance_risk_score(window: ChargerTelemetryWindow) -> float:
    """Returns a risk score in [0, 1]: how far this charger's recent abort
    and error rates exceed the baseline a healthy charger exhibits, plus
    any debounced fault-detection events, scaled so a charger at 3x the
    baseline rate (a realistic "about to fail" signal) lands around
    0.5-0.7."""
    fault_excess = (
        window.critical_fault_count * CRITICAL_FAULT_WEIGHT + window.warning_fault_count * WARNING_FAULT_WEIGHT
    )
    if window.total_sessions == 0:
        # No session history yet, but a real fault-detection layer has
        # already flagged something - don't silently report zero risk.
        score = fault_excess / (1.0 + fault_excess)
        return round(min(1.0, score), 4)

    abort_rate = window.aborted_sessions / window.total_sessions
    error_rate = window.error_count / window.total_sessions

    abort_excess = max(0.0, abort_rate - BASELINE_ABORT_RATE) / BASELINE_ABORT_RATE
    error_excess = max(0.0, error_rate - BASELINE_ERROR_RATE) / BASELINE_ERROR_RATE

    combined_excess = 0.6 * abort_excess + 0.4 * error_excess + fault_excess
    # Diminishing-returns scaling into [0, 1] instead of an unbounded ratio.
    score = combined_excess / (1.0 + combined_excess)
    return round(min(1.0, score), 4)


def is_likely_to_fail_soon(window: ChargerTelemetryWindow, threshold: float = 0.5) -> bool:
    return compute_maintenance_risk_score(window) >= threshold
