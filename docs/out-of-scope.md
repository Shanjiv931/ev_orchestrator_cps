# Out of scope / deferred items

This document records anything the build contract (`CLAUDE_CODE_MASTER_PROMPT_CPS.md`)
requires that was deliberately deferred, narrowed, or reinterpreted, and why.
Per the contract's Section 2.7, nothing required by an acceptance checklist
is left as a silent stub — if it's not built yet, it's listed here with a
reason and a plan.

## Phase 1 (repo skeleton)

Nothing deferred. All services in Section 7's repository structure exist and
boot; `docker-compose.yml` defines every service in Section 6's stack.

## Phase 2 (simulation layer)

`simulation/event_stress_sim.py` (listed in Section 7's repo tree) is not
built in this phase. It implements the mass-gathering stress-test mode,
which is a Section 5.6 beyond-scope module, not part of the core Section 4.4
simulated hardware layer - it is built in Phase 6 alongside the rest of
Section 5, once the core simulators it stresses (station_sim, swap_sim,
grid_sim) already exist to be stressed.

Everything else in Section 4.4 is built and verified live: two real-OSM SUMO
scenarios (`sim-city`, `sim-corridor`), per-station-type SimPy queueing with
the reported-vs-verified trust layer, swap-kiosk battery inventory, one
independent pandapower network per grid feeder fed by live charger/swap
draw, and a diurnal solar curve per solar-equipped site - all confirmed
publishing real data on their MQTT topics via `mosquitto_sub` before any
backend code was written, per Section 9's build order.

_Entries for later phases are appended here as they occur, not written in
advance._
