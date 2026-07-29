# Patent notes: the two control-method algorithms

Per the build contract's Section 2.5, these two algorithms must be framed and
implemented as control methods with a measurable technical effect — they
regulate a simulated physical quantity (current/voltage into a simulated
battery) against a checkable physical constraint, not just process data.

This document is completed in Phase 5, alongside the implementation of
`backend/ml/charge_controller.py` and `backend/ml/battery_health.py`. It will
describe, for each algorithm:

1. **Technical field** — battery charge-rate control / battery health
   estimation for EV fleets.
2. **Control loop** — inputs (measured/simulated state), the constrained
   optimization performed, and the physical output (charge current/voltage
   setpoint) that is applied back to the simulated cell model.
3. **Measurable technical effect** — the specific, testable invariant the
   control method guarantees (e.g. cell temperature never exceeds a hard
   ceiling; degradation cost is reduced vs. a naive baseline under identical
   conditions), each backed by an automated test in `backend/tests/`.
4. **Novelty framing** — for the battery health advisory, the cross-twin
   population query that sharpens a single vehicle's RUL estimate beyond
   what an isolated BMS could produce.

Placeholder — populated with the concrete algorithm description once Phase 5
lands (tracked as Phase 5 in `docs/architecture.md#build-order`).
