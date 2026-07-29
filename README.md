# EV Charging Orchestrator

A fully simulated, zero-cost, city-scale digital twin of an AI-driven EV
charging orchestration platform for India. Every physical thing a real
deployment needs — EVs, traffic, charging stations, battery swap points, the
electrical grid — is replaced by a realistic open-source simulator producing
the same shape of data real hardware would.

See [`docs/architecture.md`](docs/architecture.md) for the full system design,
[`docs/out-of-scope.md`](docs/out-of-scope.md) for what's deliberately
deferred and why, and [`docs/patent-notes.md`](docs/patent-notes.md) for the
two core control-method algorithms.

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

Once the stack is up:

| Service | URL |
|---|---|
| Backend API | http://localhost:8000/health |
| Frontend | http://localhost:5173 |
| Twin engine | http://localhost:8100 |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |

## Repository layout

```
ev-orchestrator/
├── simulation/       # SUMO/TraCI traffic+EV sim, SimPy station/swap sims, pandapower grid sim
├── twin-engine/       # MQTT-fed live digital twin, Redis-cached, WebSocket read API
├── backend/           # FastAPI app + the 5 core AI/ML models
├── frontend-web/       # React + TS + Vite PWA (admin + user views, i18n)
├── infra/               # Postgres init, Prometheus, Grafana provisioning
└── docs/                 # architecture, API spec, patent notes, security notes
```

## Build status

This project is built in the phase order documented in
[`docs/architecture.md`](docs/architecture.md#build-order). Phase 1 (this
skeleton) is complete; later phases land as separate commits.

## Zero-cost guarantee

No paid API, paid cloud tier, paid model inference, paid map tile, or license
fee is used anywhere in this stack. Every dependency is MIT/BSD/Apache-2.0/
GPL/EPL licensed open-source software, runnable fully offline after images are
pulled once.
