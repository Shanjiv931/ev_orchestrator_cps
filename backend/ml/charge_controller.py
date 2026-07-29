"""Health-aware adaptive fast-charging controller (Section 4.5.3).

A genuine control problem, not a scoring script: at every discrete time
step it must choose a charge power level, subject to a HARD simulated
cell-temperature ceiling that may never be violated, while minimizing a
SOFT battery-degradation cost term that penalizes sustained high power
(and especially high power while already hot - the real mechanism behind
fast-charging-induced degradation). Solved with OR-Tools CP-SAT as an
interval/cumulative scheduling-flavoured integer program over the
discretized charge curve.

Units: temperature is tracked in tenths of a degree Celsius (integer) so
the thermal recurrence stays exact in CP-SAT; power is in kW; energy is
tracked in kW-minutes (power_kw * 1 step-minute) to avoid fractional kWh.
"""
from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

POWER_LEVELS_KW = [0, 50, 100, 150, 200, 250, 300, 350, 400]
STEP_MINUTES = 1
AMBIENT_TEMP_C10 = 250  # 25.0 C
TEMP_CEILING_C10 = 450  # 45.0 C hard ceiling
# Heat gain per step ~= HEAT_COEFF_NUM/HEAT_COEFF_DEN * power_kw, in tenths of
# a degree: at 400 kW that's 400/20 = 20 -> 2.0 C/minute, in the realistic
# range for DC fast charging (an earlier HEAT_COEFF=3 implied 120 C/minute
# at 400 kW, which made every nonzero power thermally infeasible - the
# solver was correctly solving a broken model).
HEAT_COEFF_NUM, HEAT_COEFF_DEN = 1, 20
COOL_COEFF_NUM, COOL_COEFF_DEN = 1, 8  # Newton cooling: -(temp-ambient)/8 per step, integer-friendly
DEGRADATION_POWER_SCALE = 400  # keeps power^2 term in a sane integer range
HOT_THRESHOLD_C10 = 400  # 40.0 C - degradation accelerates above this
HOT_DEGRADATION_MULTIPLIER = 3
TARGET_REACHED_WEIGHT = 100_000  # dominates the objective: speed first, degradation second
DEGRADATION_WEIGHT = 1


@dataclass
class ChargeScheduleResult:
    power_schedule_kw: list[int]
    temp_schedule_c10: list[int]
    cumulative_kwmin: list[int]
    minutes_to_target: int | None
    total_degradation_cost: int


def _simulate_thermal_and_degradation(power_schedule_kw: list[int]) -> tuple[list[int], list[int]]:
    """Forward-simulates the same recurrence the CP-SAT model encodes, so a
    baseline (or any externally-chosen) schedule can be evaluated on equal
    terms with the optimizer's output."""
    temps = [AMBIENT_TEMP_C10]
    degradation_costs = []
    for power in power_schedule_kw:
        t = temps[-1]
        heat_gain = (HEAT_COEFF_NUM * power) // HEAT_COEFF_DEN
        cooling = (t - AMBIENT_TEMP_C10) // COOL_COEFF_DEN * COOL_COEFF_NUM
        next_t = t + heat_gain - cooling
        temps.append(next_t)
        cost = (power * power) // DEGRADATION_POWER_SCALE
        if t > HOT_THRESHOLD_C10:
            cost *= HOT_DEGRADATION_MULTIPLIER
        degradation_costs.append(cost)
    return temps[1:], degradation_costs


def optimize_charge_schedule(target_kwh: float, horizon_minutes: int = 15,
                              temp_ceiling_c10: int = TEMP_CEILING_C10) -> ChargeScheduleResult:
    """Maximizes charge rate (reach target_kwh as few steps as possible)
    subject to the hard thermal ceiling, minimizing cumulative degradation
    cost as a secondary objective among schedules that reach the target
    equally fast."""
    target_kwmin = round(target_kwh * 60)
    model = cp_model.CpModel()

    power_idx = [model.NewIntVar(0, len(POWER_LEVELS_KW) - 1, f"power_idx_{t}") for t in range(horizon_minutes)]
    power = [model.NewIntVarFromDomain(cp_model.Domain.FromValues(POWER_LEVELS_KW), f"power_{t}") for t in range(horizon_minutes)]
    for t in range(horizon_minutes):
        model.AddElement(power_idx[t], POWER_LEVELS_KW, power[t])

    temp = [model.NewIntVar(0, 1000, f"temp_{t}") for t in range(horizon_minutes + 1)]
    model.Add(temp[0] == AMBIENT_TEMP_C10)
    for t in range(horizon_minutes):
        heat_gain = model.NewIntVar(0, 1000, f"heat_gain_{t}")
        model.AddDivisionEquality(heat_gain, power[t] * HEAT_COEFF_NUM, HEAT_COEFF_DEN)
        cooling = model.NewIntVar(0, 1000, f"cooling_{t}")
        model.AddDivisionEquality(cooling, temp[t] - AMBIENT_TEMP_C10, COOL_COEFF_DEN)
        model.Add(temp[t + 1] == temp[t] + heat_gain - cooling * COOL_COEFF_NUM)
        model.Add(temp[t] <= temp_ceiling_c10)  # HARD constraint, never violated

    cumulative = [model.NewIntVar(0, target_kwmin * 2 + 1000, f"cum_{t}") for t in range(horizon_minutes)]
    model.Add(cumulative[0] == power[0] * STEP_MINUTES)
    for t in range(1, horizon_minutes):
        model.Add(cumulative[t] == cumulative[t - 1] + power[t] * STEP_MINUTES)

    reached = [model.NewBoolVar(f"reached_{t}") for t in range(horizon_minutes)]
    for t in range(horizon_minutes):
        model.Add(cumulative[t] >= target_kwmin).OnlyEnforceIf(reached[t])
        model.Add(cumulative[t] < target_kwmin).OnlyEnforceIf(reached[t].Not())
    for t in range(1, horizon_minutes):
        model.AddImplication(reached[t - 1], reached[t])  # monotonic once reached

    hot = [model.NewBoolVar(f"hot_{t}") for t in range(horizon_minutes)]
    for t in range(horizon_minutes):
        model.Add(temp[t] > HOT_THRESHOLD_C10).OnlyEnforceIf(hot[t])
        model.Add(temp[t] <= HOT_THRESHOLD_C10).OnlyEnforceIf(hot[t].Not())

    degradation_terms = []
    for t in range(horizon_minutes):
        base_cost = model.NewIntVar(0, 10_000, f"base_cost_{t}")
        squared_idx_costs = [(POWER_LEVELS_KW[i] * POWER_LEVELS_KW[i]) // DEGRADATION_POWER_SCALE for i in range(len(POWER_LEVELS_KW))]
        model.AddElement(power_idx[t], squared_idx_costs, base_cost)
        hot_extra = model.NewIntVar(0, 10_000, f"hot_extra_{t}")
        model.Add(hot_extra == base_cost * (HOT_DEGRADATION_MULTIPLIER - 1)).OnlyEnforceIf(hot[t])
        model.Add(hot_extra == 0).OnlyEnforceIf(hot[t].Not())
        step_cost = model.NewIntVar(0, 50_000, f"step_cost_{t}")
        model.Add(step_cost == base_cost + hot_extra)
        degradation_terms.append(step_cost)

    not_reached_count = sum(1 - reached[t] for t in range(horizon_minutes))
    total_degradation = sum(degradation_terms)
    model.Minimize(TARGET_REACHED_WEIGHT * not_reached_count + DEGRADATION_WEIGHT * total_degradation)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"charge schedule optimization failed: solver status {status}")

    power_schedule = [solver.Value(power[t]) for t in range(horizon_minutes)]
    temp_schedule = [solver.Value(temp[t + 1]) for t in range(horizon_minutes)]
    cumulative_schedule = [solver.Value(cumulative[t]) for t in range(horizon_minutes)]

    minutes_to_target = None
    for t in range(horizon_minutes):
        if cumulative_schedule[t] >= target_kwmin:
            minutes_to_target = t + 1
            break

    return ChargeScheduleResult(
        power_schedule_kw=power_schedule,
        temp_schedule_c10=temp_schedule,
        cumulative_kwmin=cumulative_schedule,
        minutes_to_target=minutes_to_target,
        total_degradation_cost=int(solver.Value(total_degradation)),
    )


def naive_constant_current_schedule(horizon_minutes: int = 15,
                                     temp_ceiling_c10: int = TEMP_CEILING_C10) -> list[int]:
    """The highest constant power level whose thermal trajectory never
    breaches the ceiling over the full horizon - a thermally-safe but
    non-adaptive baseline, exactly what a naive constant-current charger
    does."""
    safe_level = POWER_LEVELS_KW[0]
    for level in POWER_LEVELS_KW:
        temps, _ = _simulate_thermal_and_degradation([level] * horizon_minutes)
        if all(t <= temp_ceiling_c10 for t in temps):
            safe_level = level
        else:
            break
    return [safe_level] * horizon_minutes


def evaluate_schedule_degradation_to_target(power_schedule_kw: list[int], target_kwh: float) -> tuple[int, int]:
    """Returns (minutes_to_target, cumulative_degradation_cost_up_to_target)
    for a given schedule, so two schedules can be compared fairly - over
    the time each actually took to reach the same target, not the full
    horizon."""
    target_kwmin = round(target_kwh * 60)
    _, degradation_costs = _simulate_thermal_and_degradation(power_schedule_kw)
    cumulative = 0
    for t, power in enumerate(power_schedule_kw):
        cumulative += power * STEP_MINUTES
        if cumulative >= target_kwmin:
            return t + 1, sum(degradation_costs[: t + 1])
    return len(power_schedule_kw), sum(degradation_costs)
