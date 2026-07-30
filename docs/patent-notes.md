# Patent notes: the two control-method algorithms

Per the build contract's Section 2.5, these two algorithms are framed and
implemented as **control methods with a measurable technical effect** -
each regulates a simulated physical quantity against a checkable physical
constraint, rather than merely scoring or classifying data. Both are
implemented in `backend/ml/` and verified by automated tests that assert
the technical effect directly, not just that a function returns a value.

## 1. Health-aware adaptive fast-charging controller

**Code:** `backend/ml/charge_controller.py`, function
`optimize_charge_schedule`. Tests: `backend/tests/test_charge_controller.py`.

**Technical field.** Real-time regulation of DC fast-charging power
delivered to an EV battery pack, at the granularity of the charge
controller's own control loop (modeled here at 1-minute resolution over a
13-20 minute charging session).

**Control loop.**
- *Input state each step*: the battery's current simulated cell
  temperature (`temp[t]`, tracked in tenths of a degree via an integer
  thermal recurrence) and cumulative energy delivered so far
  (`cumulative[t]`, in kW-minutes).
- *Decision variable each step*: a discrete charge power level
  `power[t]` drawn from a fixed set of physically realistic levels (0-400
  kW), chosen by an OR-Tools CP-SAT solve over the whole session horizon
  at once (not a greedy per-step choice).
- *Physical output*: the chosen `power[t]` is the setpoint that would be
  applied back to the simulated cell model as current/voltage command -
  precisely the quantity a real BMS/charger control loop regulates.
- *Hard constraint*: `temp[t] <= temp_ceiling_c10` for every step, encoded
  directly in the CP-SAT model (not filtered after the fact). This is
  checkable against a physical limit exactly as the contract requires:
  `test_thermal_ceiling_is_never_violated_in_the_target_scenario` and
  `test_hard_ceiling_actually_forces_throttling_under_thermal_stress`
  assert it holds under both a normal and a deliberately tightened
  ceiling, the latter proving the constraint is load-bearing (forces the
  solver below max power), not merely present and unused.
- *Soft constraint*: a degradation-cost penalty term (quadratic in power,
  amplified further above a "hot" temperature threshold - modeling the
  real mechanism by which sustained high-power charging while already hot
  accelerates cell degradation) is added to the objective as a secondary
  term behind the primary speed objective.

**Measurable technical effect.** Two effects are each backed by a
dedicated automated test:
1. The thermal ceiling is *never* violated, under normal operation and
   under an adversarial tightened ceiling that forces real throttling
   (`max(power_schedule_kw) < 400` in that scenario - a directly
   observable, checkable output).
2. For a fixed target (90 kWh, 10%->80% of a large pack) reached in the
   same 14 minutes as a naive constant-current baseline, the controller's
   cumulative degradation cost is measurably lower
   (`test_optimized_schedule_reduces_degradation_vs_naive_at_equal_speed`)
   - the control method produces a better physical outcome (less cell
   stress) for an identical task, not just a different number.

## 2. Battery Health & Replacement Advisory (cross-twin RUL estimation)

**Code:** `backend/ml/battery_health.py`. Tests:
`backend/tests/test_battery_health_ml.py`.

**Technical field.** Estimation of a battery pack's remaining useful life
(RUL) - months until State-of-Health (SoH) crosses an 80%-capacity
replacement threshold - from simulated usage stressors and a population
of comparable battery twins.

**Control-relevant framing.** Unlike the charge controller, this module
does not itself actuate a physical setpoint; its "control effect" is on
the *estimate* fed into deployment decisions (when to schedule
replacement, how aggressively to allow fast-charging for a given pack).
The measurable technical effect required by the contract is that this
estimate is *checkable against a ground-truth quantity* and *demonstrably
more accurate* than the single-vehicle-only alternative - which is
exactly what `test_population_query_sharpens_rul_estimate_beyond_individual_only`
asserts: given a vehicle with only two noisy historical records
(individually implying a wildly wrong degradation slope), blending that
estimate with a population slope drawn from other twins of the same
chemistry/vehicle class via a real SQL query (`population_degradation_slope`,
not a description of the idea) produces a projection measurably closer to
the true underlying trend than the individual-only estimate.

**Why this is the differentiating piece, not the SoH formula itself.**
`estimate_soh_pct` is a straightforward empirical function (real,
monotonic, tested) but not novel. The cross-twin population query -
treating every other vehicle's history in the same fleet as additional
evidence for one vehicle's own RUL, shrunk toward the individual estimate
in proportion to how much of that vehicle's own data exists - is the
mechanism a single isolated BMS cannot reproduce, since it has no access
to other vehicles' histories at all.

## Novelty framing, in one sentence each

- **Charge controller**: a constrained-optimization control loop that
  jointly schedules charge power to satisfy a hard thermal safety
  invariant while minimizing degradation cost as a secondary objective,
  verified to force real throttling under stress rather than only
  asserting compliance in the unconstrained case.
- **Battery health advisory**: an empirical-Bayes shrinkage estimator that
  combines a vehicle's own (possibly sparse) degradation history with a
  live population query across twins of matching chemistry/usage profile,
  verified to reduce estimation error versus the single-vehicle baseline
  on a constructed adversarial case.
