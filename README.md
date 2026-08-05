# MeridianGrid

A fully simulated, zero-cost, city-scale digital twin of an AI-driven EV
charging orchestration platform for Vellore, Tamil Nadu. Every physical thing
a real deployment needs — EVs, traffic, charging stations, battery swap
points, the electrical grid, and per-port fault detection — is replaced by a
realistic open-source simulator producing the same shape of data real
hardware would, and every layer built on top of that data (the twin, the AI
models, the APIs, the dashboards) is written exactly as it would be for a
real deployment.

The simulation layer is SUMO-only, built from real Vellore OpenStreetMap
road-network data — there is no 3D driving client. This project is being
prepared for academic publication, and a reproducible, headless, parameterized
simulation is what a methodology/evaluation section needs; see
[`docs/vellore-expansion.md`](docs/vellore-expansion.md) for the full
rationale, the scenario taxonomy, and a stakeholder problem→system-response
mapping table.

See [`docs/architecture.md`](docs/architecture.md) for the full system
design, [`docs/vellore-expansion.md`](docs/vellore-expansion.md) for the
Vellore-focused expansion (scenario taxonomy, weather advisory, embedded
fault-detection layer, reservations, admin RBAC, and an explicit
Limitations section), [`docs/out-of-scope.md`](docs/out-of-scope.md) for
what's deliberately deferred (and why), [`docs/patent-notes.md`](docs/patent-notes.md)
for the two core control-method algorithms, [`docs/security-notes.md`](docs/security-notes.md)
for the MQTT/OCPP signing design and DPDP retention job, and
[`docs/api-spec.yaml`](docs/api-spec.yaml) for the OpenAPI spec (a work in
progress — it currently documents a subset of the live routes; see the
Limitations section of `docs/vellore-expansion.md`).

## Prerequisites

- Docker + Docker Compose
- Docker Desktop (or an equivalent daemon) running

## Quickstart

```bash
git clone <this-repo>
cd ev-orchestrator
docker compose up
```

No `.env` file is required — every variable in [`.env.example`](.env.example)
already has a working local default. Copy it to `.env` only if you want to
override a port, credential, or set `RANDOM_SEED` for a reproducible run
(needed to re-derive the same numbers a paper's results section reports).

Once the stack is up (give the SUMO scenarios and simulators ~15 seconds to
start producing telemetry):

| Service | URL |
|---|---|
| Frontend (register/login here) | http://localhost:5173 |
| Backend API | http://localhost:8000/health |
| Backend interactive API docs | http://localhost:8000/docs |
| Live results/evaluation snapshot | http://localhost:8000/simulation/report |
| Twin engine (internal) | http://localhost:8100 |
| Grafana (admin/admin) | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

The frontend starts pre-seeded with 13 real Vellore-area stations (VIT
University, Katpadi, CMC Hospital, Vellore Fort, Bagayam, Sathuvachari,
Gandhi Nagar, Thorapadi, Officers Line, Chittoor Road, Green Circle, Arni
Road, plus an outskirts village kiosk) — the live map and admin
grid/feeder dashboard populate from the simulation layer immediately.

## What's actually running

16 containers, all defined in `docker-compose.yml`, all with no manual setup:

- **`sim-city` / `sim-corridor` / `sim-vellore`** — three SUMO/TraCI
  scenarios: two generic OSM-extract scenarios (a dense city grid and a
  sparse highway corridor) plus the real Vellore town network, each vehicle
  mapped to a realistic Indian EV profile (2W/3W/4W, connector type, battery
  chemistry) with a battery that depletes with distance travelled.
- **`sim-station` / `sim-swap` / `sim-grid` / `sim-solar`** — SimPy queueing
  per station type with a reported-vs-verified trust layer and full OCPP
  StatusNotification/MeterValues electrical telemetry (voltage, current,
  power factor, temperature), battery-swap kiosks as a battery-inventory
  problem, one independent pandapower network per real Vellore grid feeder
  (9 feeder zones), and a diurnal solar generation curve.
- **`sim-charger-monitor`** — the simulated embedded fault-detection layer
  (a software-simulated Charger Monitoring Unit, conceptually equivalent to
  a microcontroller sampling current/temperature/voltage/earth-leakage/
  Control Pilot signal lines): threshold detection with debouncing, real
  OCPP StatusNotification ErrorCode vocabulary and IEC 61851 Control Pilot
  states, scenario-controlled fault-injection rate. See
  [`docs/vellore-expansion.md`](docs/vellore-expansion.md#4-simulated-embedded-fault-detection-layer).
- **`twin-engine`** — subscribes to every MQTT topic, caches live state in
  Redis, exposes an internal read API and WebSocket broadcast, verified to
  reflect a new message within 1 second under real load.
- **`backend`** — FastAPI + Postgres/PostGIS/TimescaleDB, JWT auth, full CRUD
  over the core data model, 5 AI/ML models (demand forecasting, a
  trust-aware recommendation scorer, an OR-Tools health-aware fast-charge
  controller, a cross-twin battery health advisory, an OR-Tools fleet
  scheduler), a real Open-Meteo weather integration with a rules-based
  charging-time advisory, a live fault-detection consumer that closes the
  loop from a simulated fault to a real charger's status and predictive
  maintenance risk score, a port reservation system, an axis-based scenario
  engine (traffic/weather/grid-stress/fault-injection-rate), an aggregate
  `/simulation/report` endpoint for pulling live numbers straight into a
  paper's results section, 10 beyond-scope modules (V2G/V2H, blackout
  resilience, solar-synced charging, safety score, emergency queueing,
  mass-gathering stress test with fault-informed capacity derating,
  simulated pay-at-station, carbon/ESG tracking, predictive maintenance,
  rural mini-grid capacity planning), an audit-logged RBAC-restricted admin
  database console, Prometheus metrics, and a DPDP data-retention job.
- **`frontend-web`** — React + TypeScript + Vite PWA, English-only,
  offline-first, persona-based default views (individual driver, fleet
  operator, housing-society resident, Vellore city admin), a live map with
  port reservation and a weather-aware charging advisory, and an admin
  dashboard with real Vellore feeder/station data, live per-charger fault
  status, and the RBAC-restricted database console.
- **`postgres`, `redis`, `mosquitto`, `prometheus`, `grafana`** — the
  supporting infrastructure, all open-source, all self-hosted.

`godot-viewer/` is a standalone, optional 3D visualization of the live
Vellore SUMO telemetry (MQTT → WebSocket relay → Godot scene) - not part of
`docker compose up`, not required for the platform to work, and launched
manually only if a 3D view of the twin is wanted alongside the primary
2D/dashboard experience.

## Repository layout

```
ev-orchestrator/
├── simulation/       # SUMO/TraCI traffic+EV sim, SimPy station/swap/grid/solar sims,
│                      # the embedded fault-detection layer, Vellore registry
├── twin-engine/       # MQTT-fed live digital twin, Redis-cached, WebSocket read API
├── backend/           # FastAPI app, database, the 5 core AI/ML models, 10 beyond-scope
│                      # modules, weather/advisory/fault-consumer services
├── frontend-web/       # React + TS + Vite PWA (persona-based views, offline-first)
├── godot-viewer/       # Optional standalone 3D twin viewer (not containerized)
├── infra/               # Postgres init, Prometheus config, Grafana provisioning
└── docs/                 # architecture, Vellore expansion, API spec, patent notes,
                            # security notes, out-of-scope
```

## Running the tests

```bash
# Backend (5 core models + 10 beyond-scope modules + CRUD + auth + fault
# detection + reservations + admin RBAC) - needs a local Postgres reachable
# at localhost:5432; docker compose up already provides one, or point
# POSTGRES_DSN at your own.
cd backend && pip install -r requirements.txt && pytest

# Simulation layer (SUMO/TraCI, SimPy sims, the fault-detection state machine)
cd simulation && pip install -r requirements.txt && pytest tests/

# Digital twin engine (pure-logic tests always run; two tests skip
# automatically unless the full stack is up, verifying the <1s freshness
# guarantee against it live)
cd twin-engine && pip install -r requirements.txt && pytest tests/

# Frontend
cd frontend-web && npm ci && npm run test
```

CI (`.github/workflows/ci.yml`) runs all of the above plus a frontend build
and a `docker compose config` validation on every push.

## Reproducibility

Every simulation process that uses randomness (SUMO route/departure
patterns, station/swap queueing, grid feeder noise, the fault-detection
layer) honors an optional `RANDOM_SEED` environment variable. Unset (the
default) keeps genuine run-to-run variation for a live demo; set to any
integer and every process becomes reproducible - needed to re-derive the
same numbers a paper's evaluation section reports. See
[`.env.example`](.env.example).

## Build order

Built in the phase order documented in
[`docs/architecture.md`](docs/architecture.md#build-order), each phase
verified live against a running stack before moving to the next - not just
written and assumed to work. The Vellore SUMO expansion (scenario taxonomy,
weather advisory, fault-detection layer, reservations, admin RBAC) is
documented separately in [`docs/vellore-expansion.md`](docs/vellore-expansion.md).

## Zero-cost guarantee

No paid API, paid cloud tier, paid model inference, paid map tile, or license
fee is used anywhere in this stack - including the real weather integration,
which uses Open-Meteo (free, no API key). Every dependency is MIT/BSD/
Apache-2.0/GPL/EPL licensed open-source software, runnable fully offline
after images are pulled once. `docs/out-of-scope.md` documents every
dependency-related tradeoff made along the way (a couple of `npm audit`
flags judged inapplicable to how this app actually uses those libraries,
and why).
