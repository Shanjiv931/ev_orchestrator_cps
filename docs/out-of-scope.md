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

## Phase 5 (AI/ML layer)

`demand_forecast.py` uses XGBoost, not an LSTM - Section 4.5.1 explicitly
allows either, and XGBoost is the better fit for this project's
constraints: CPU-only, zero-cost, fast to train and test, and the
zone/hour/day/weather feature set is tabular rather than a long sequence
an RNN would meaningfully exploit.

`recommendation.py` and `fleet_scheduler.py` don't yet read live data from
the twin store or Postgres - they operate on `Candidate`/`DepotVehicle`
dataclasses passed in by the caller. Wiring them to real backend queries
(nearby compatible stations from PostGIS, depot vehicles from the
`vehicles` table filtered by `fleet_depot_id`) happens in Phase 6/7 when
there are API endpoints that actually need to call them.

`fleet_scheduler.py`'s per-vehicle-per-charger duration is computed from a
simple energy/power division, not a full physical charge curve (unlike
`charge_controller.py`, which does model the curve) - reasonable for a
batch scheduling decision where the binding constraints are charger/feeder
capacity, not second-by-second thermal behavior.

## Phase 6 (beyond-scope modules)

Multilingual/low-literacy frontend and offline-first PWA behavior (Section
5 items 7 and 8) are deferred to Phase 7 - they have no backend component
at all, being entirely about how the frontend renders and caches, so
building them now would mean building them twice.

`rural_minigrid.py` has no dedicated API endpoint yet, unlike the other
nine backend modules - it's a capacity-planning function meant to back an
admin-facing "can this village feeder handle N more EVs" tool, which
belongs with the rest of the admin dashboard in Phase 7 rather than as a
standalone endpoint with no UI consumer yet.

The emergency-queue and V2G/blackout endpoints are stateless/in-memory for
now (`advanced_features.py`'s `_priority_jump_trackers` dict, and V2G
vehicle eligibility supplied directly in the request body rather than
read from the `vehicles` table). Real queues live at actual chargers/swap
slots (Phase 4's `Charger`/`SwapSlot` tables) and V2G-relevant vehicle
attributes (opted_in, v2g_capable) don't exist in the Section 8 schema -
wiring these to persistent state is Phase 7 work, once the frontend
defines what a real request/response cycle for these features looks like.

## Phase 7 (frontend)

`react-router-dom` is on the latest 7.x despite `npm audit` flagging a high
severity advisory (GHSA-qwww-vcr4-c8h2) in that range: the advisory is
specifically a CSRF bypass in RSC (React Server Components) *mode*. This
app is a plain client-side Vite SPA using `createBrowserRouter`-style
routing with no RSC, no framework data mode, no server actions - the
vulnerable code path doesn't exist in how this app uses the library.
Downgrading to the one non-flagged version (7.11.0) turned out to
re-trigger a *different* advisory in the opposite direction when tested,
suggesting the two advisories' ranges don't leave a clean gap; latest was
judged the better tradeoff (most bug fixes, inapplicable CVE) over an
older version with its own flagged issues.

`vite-plugin-pwa` (and transitively `workbox-build`) also has flagged
dev-time-only dependencies (old `rollup-plugin-off-main-thread`,
`brace-expansion`, `ejs`, `filelist`, `jake`, `minimatch`). These run only
during `vite build`/`npm run dev`, never ship to the browser bundle, and
the only realistic exploit path requires already controlling the dev
machine's build inputs - accepted rather than forcing a major-version
downgrade of the PWA plugin for a local, zero-cost academic project.

The DB-backed `stations`/`chargers` (Phase 4 schema, what the frontend
renders as static infrastructure) and the simulation layer's own
`registry.py` stations (Phase 2, what actually publishes live MQTT
telemetry) are two independent datasets with no shared identifier - the
frontend was seeded with a handful of demo stations via the API for a
working UI, but their `chargers[].status` won't reflect the simulator's
live per-charger state the way `/twin/feeder` genuinely does for grid
load. Unifying them (e.g. a sync job, or having the simulator write
through the backend's own CRUD instead of only MQTT) is real integration
work for a future pass, not required by the Section 11 checklist as
written.

No frontend equivalent of "safety-score-driven ranking flip" or
"emergency-priority queue jump" has its own dedicated UI beyond what
`StationsPage`/`SessionsPage` already expose (a checkbox for
solo-traveler context and emergency priority, respectively, both wired to
real backend behavior already tested in Phase 6). A richer visual
treatment (e.g. a red safety badge, a queue-position indicator) is
possible polish, not a functional gap.

Docker Desktop's Windows bind mount doesn't reliably forward file-change
events into the container, so Vite's default `chokidar` watcher can miss
edits entirely - no error, just silently stale HMR (a real instance of
this: a station safety-score badge's contrast fix was edited, tests and
`npm run build` both passed against the edited file, but the running dev
container kept serving the pre-edit version until `server.watch.usePolling`
was added to `vite.config.ts`). Anyone developing on Windows should expect
this and know the fix already exists in the committed config.

_Entries for later phases are appended here as they occur, not written in
advance._
