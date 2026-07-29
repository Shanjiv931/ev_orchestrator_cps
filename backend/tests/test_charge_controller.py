from ml.charge_controller import (
    evaluate_schedule_degradation_to_target,
    naive_constant_current_schedule,
    optimize_charge_schedule,
)


def test_thermal_ceiling_is_never_violated_in_the_target_scenario():
    # ~90 kWh: 10%->80% of a large (~130 kWh) fast-charge-capable 4W pack.
    result = optimize_charge_schedule(target_kwh=90.0, horizon_minutes=18)
    assert all(temp <= 450 for temp in result.temp_schedule_c10)


def test_reaches_target_within_the_fastest_2026_tier_window():
    """Section 4.5.3: 10%->80% in roughly 13-15 minutes at the 350-400 kW tier."""
    result = optimize_charge_schedule(target_kwh=90.0, horizon_minutes=18)
    assert result.minutes_to_target is not None
    assert 13 <= result.minutes_to_target <= 15
    assert max(result.power_schedule_kw) >= 350


def test_optimized_schedule_reduces_degradation_vs_naive_at_equal_speed():
    target_kwh = 90.0
    result = optimize_charge_schedule(target_kwh=target_kwh, horizon_minutes=18)
    naive = naive_constant_current_schedule(horizon_minutes=18)

    naive_minutes, naive_degradation = evaluate_schedule_degradation_to_target(naive, target_kwh)
    opt_minutes, opt_degradation = evaluate_schedule_degradation_to_target(result.power_schedule_kw, target_kwh)

    assert opt_minutes == naive_minutes  # fair comparison: same time-to-target
    assert opt_degradation < naive_degradation


def test_hard_ceiling_actually_forces_throttling_under_thermal_stress():
    """Proves the hard constraint isn't vacuous: under a tight ceiling, the
    optimizer must back off power below the max level to stay compliant,
    and never exceeds the ceiling even while doing so."""
    tight_ceiling = 350  # 35.0 C
    result = optimize_charge_schedule(target_kwh=60.0, horizon_minutes=25, temp_ceiling_c10=tight_ceiling)

    assert all(temp <= tight_ceiling for temp in result.temp_schedule_c10)
    assert max(result.power_schedule_kw) < 400  # forced to throttle below max
    assert min(t for t in result.temp_schedule_c10 if t > 0) < tight_ceiling  # not just sitting at 0 the whole time


def test_naive_baseline_under_tight_ceiling_is_more_conservative_than_optimizer():
    """A naive constant-current charger must pick one safe level for the
    whole session (accounting for the steady-state temperature), so it ends
    up far more conservative than a controller that can actively adapt."""
    tight_ceiling = 350
    naive = naive_constant_current_schedule(horizon_minutes=25, temp_ceiling_c10=tight_ceiling)
    result = optimize_charge_schedule(target_kwh=60.0, horizon_minutes=25, temp_ceiling_c10=tight_ceiling)

    assert naive[0] < max(result.power_schedule_kw)


def test_optimizer_stops_drawing_power_once_target_is_reached():
    result = optimize_charge_schedule(target_kwh=90.0, horizon_minutes=18)
    reached_at = result.minutes_to_target
    assert all(p == 0 for p in result.power_schedule_kw[reached_at:])
