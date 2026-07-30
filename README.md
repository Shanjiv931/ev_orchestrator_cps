# EV Charging Orchestrator

A fully simulated, zero-cost, city-scale digital twin of an AI-driven EV
charging orchestration platform for India. Every physical thing a real
deployment needs — EVs, traffic, charging stations, battery swap points, the
electrical grid — is replaced by a realistic open-source simulator producing
the same shape of data real hardware would, and every layer built on top of
that data (the twin, the AI models, the APIs, the dashboards) is written
exactly as it would be for a real deployment.

See [`docs/architecture.md`](docs/architecture.md) for the full system
design, [`docs/out-of-scope.md`](docs/out-of-scope.md) for what's
deliberately deferred (and why), [`docs/patent-notes.md`](docs/patent-notes.md)
for the two core control-method algorithms, [`docs/security-notes.md`](docs/security-notes.md)
for the MQTT/OCPP signing design and DPDP retention job, and
[`docs/api-spec.yaml`](docs/api-spec.yaml) for the generated OpenAPI spec.

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
override a port or credential.

Once the stack is up (give the SUMO scenarios and simulators ~15 seconds to
start producing telemetry):

| Service | URL |
|---|---|
| Frontend (register/login here) | http://localhost:5173 |
| Backend API | http://localhost:8000/health |
| Backend interactive API docs | http://localhost:8000/docs |
| Twin engine (internal) | http://localhost:8100 |
| Grafana (admin/admin) | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

The frontend starts empty (no stations exist until you or a seed script
create them via the API — see `POST /stations` in the API docs above); the
live map and grid-stress dashboard populate from the simulation layer
immediately regardless.

## What's actually running

13 containers, all defined in `docker-compose.yml`, all with no manual setup:

- **`sim-city` / `sim-corridor`** — two SUMO/TraCI scenarios built from real
  OpenStreetMap extracts (a dense Koramangala, Bengaluru city scenario and a
  sparse NH48 highway-corridor scenario), each vehicle mapped to a realistic
  Indian EV profile with a battery that depletes with distance travelled.
- **`sim-station` / `sim-swap` / `sim-grid` / `sim-solar`** — SimPy queueing
  per station type with a reported-vs-verified trust layer, battery-swap
  kiosks as a battery-inventory problem, one independent pandapower network
  per grid feeder, and a diurnal solar generation curve.
- **`twin-engine`** — subscribes to every MQTT topic, caches live state in
  Redis, exposes an internal read API and WebSocket broadcast, verified to
  reflect a new message within 1 second under real load.
- **`backend`** — FastAPI + Postgres/PostGIS/TimescaleDB, JWT auth, full CRUD
  over the Section 8 data model, the 5 AI/ML models (demand forecasting,
  a trust-aware recommendation scorer, an OR-Tools health-aware fast-charge
  controller, a cross-twin battery health advisory, an OR-Tools fleet
  scheduler), 10 beyond-scope modules (V2G/V2H, blackout resilience,
  solar-synced charging, safety score, emergency queueing, mass-gathering
  stress test, simulated UPI payments, carbon/ESG tracking, predictive
  maintenance, rural mini-grid capacity planning), Prometheus metrics, and a
  DPDP data-retention job.
- **`frontend-web`** — React + TypeScript + Vite PWA, English + Hindi,
  offline-first, persona-based default views (individual driver, fleet
  operator, housing-society resident, city admin/DISCOM viewer), a live map,
  and an admin dashboard with real demand-forecast and grid-stress charts.
- **`postgres`, `redis`, `mosquitto`, `prometheus`, `grafana`** — the
  supporting infrastructure, all open-source, all self-hosted.

## Repository layout

```
ev-orchestrator/
├── simulation/       # SUMO/TraCI traffic+EV sim, SimPy station/swap/grid/solar sims
├── twin-engine/       # MQTT-fed live digital twin, Redis-cached, WebSocket read API
├── backend/           # FastAPI app, database, the 5 core AI/ML models, 10 beyond-scope modules
├── frontend-web/       # React + TS + Vite PWA (persona-based views, i18n, offline-first)
├── infra/               # Postgres init, Prometheus config, Grafana provisioning
└── docs/                 # architecture, API spec, patent notes, security notes, out-of-scope
```

## Running the tests

```bash
# Backend (5 core models + 10 beyond-scope modules + CRUD + auth) - needs a
# local Postgres reachable at localhost:5432; docker compose up already
# provides one, or point POSTGRES_DSN at your own.
cd backend && pip install -r requirements.txt && pytest

# Simulation layer
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

## Build order

Built in the phase order documented in
[`docs/architecture.md`](docs/architecture.md#build-order), each phase
verified live against a running stack before moving to the next - not just
written and assumed to work. All 9 phases are complete.

## Zero-cost guarantee

No paid API, paid cloud tier, paid model inference, paid map tile, or license
fee is used anywhere in this stack. Every dependency is MIT/BSD/Apache-2.0/
GPL/EPL licensed open-source software, runnable fully offline after images are
pulled once. `docs/out-of-scope.md` documents every dependency-related
tradeoff made along the way (a couple of `npm audit` flags judged
inapplicable to how this app actually uses those libraries, and why).
