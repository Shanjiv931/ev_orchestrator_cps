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

## Phase 3 (digital twin engine)

Nothing deferred. `twin-engine` subscribes to all five MQTT namespaces,
caches every entity in Redis, exposes a read API (`GET /state/{type}` and
`GET /state/{type}/{id}`) and a `/ws` WebSocket broadcast, and the <1s
freshness requirement is verified against the live stack in
`twin-engine/tests/test_live_latency.py`.

That test caught a real bug during development, worth recording since it
shaped the final design: the first implementation did two blocking Redis
writes per MQTT message (a `SET` plus a `SADD` into an index set for
listing). Under the simulation layer's real throughput (~100+ msgs/sec) and
Docker Desktop's WSL2-virtualized networking, that second round-trip was
enough to build an unbounded backlog, delaying twin state by minutes
instead of the required <1s. Fixed by dropping to one write per message
and listing entities via `SCAN` instead of a maintained index. Separately,
`traci_bridge.py` was stepping SUMO as fast as the CPU allowed with no
pacing, which was itself the larger source of message volume - it now
paces to real time via `--realtime-factor`.

## Phase 4 (database + core backend CRUD)

USERS gains `email` and `hashed_password` beyond the Section 8 ERD - the
ERD has no login-credential fields at all, and Section 9.4 explicitly
requires JWT auth, so this is the "strictly necessary" extension the
contract allows for.

STATIONS keeps plain `lat`/`lon` floats rather than a PostGIS geometry
column for now, even though `geoalchemy2` is in the stack. Nearest-station
queries don't exist yet (that's Phase 5's recommendation engine); a
PostGIS geometry column with a spatial index is added then, when there's
an actual query to optimize, rather than speculatively now.

Station/charger/swap-slot/feeder write endpoints have no role restriction
yet (e.g. only a city-admin persona should really be able to create a
station) - authentication exists, coarse-grained authorization does not.
Acceptable for this phase since nothing in the Section 11 acceptance
checklist requires it yet; revisit if a beyond-scope module needs it.

_Entries for later phases are appended here as they occur, not written in
advance._
