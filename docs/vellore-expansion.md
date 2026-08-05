# Vellore simulation expansion

This document covers a later expansion phase, written as a standalone
addendum rather than folded into the existing numbered `Section N`
documentation set (`architecture.md`, `out-of-scope.md`, etc.), which
cross-reference a `CLAUDE_CODE_MASTER_PROMPT_CPS.md` build contract not
present in this repository. Nothing here should be assumed to occupy a
specific section number in that external document.

## 1. Motivation and scope

The platform originally paired its SUMO-based traffic/queueing/grid
simulation (Phase 2) with a CARLA-based 3D driving simulation added in a
later session. That 3D layer has been **removed entirely** in favor of a
SUMO-only simulation, for three reasons specific to preparing this project
for academic publication:

1. A 3D driving view demonstrates the platform but doesn't strengthen a
   paper's methodology or evaluation - what does is a reproducible,
   parameterized, headless simulation whose outputs can be tabulated.
2. CARLA introduced a real, load-bearing engine bug (custom OpenDRIVE
   networks silently failed to register spawned actors) that was worked
   around by switching to CARLA's built-in Town10 map - a coordinate-mapped
   stand-in for Vellore, not Vellore's actual road network. SUMO's network
   (`simulation/sumo/vellore/`) is generated directly from real Vellore
   OpenStreetMap data, which is the more defensible ground truth for a
   paper's road-network and traffic claims.
3. GPU/hardware dependence (CARLA needs a discrete GPU) is a poor fit for a
   simulation meant to be independently re-run by reviewers.

This expansion adds four substantive new capabilities on top of the
existing platform - a formal scenario taxonomy, real weather integration
with a rules-based charging advisory, a simulated embedded fault-detection
layer, and a charger reservation system - plus fixes a real data-integrity
bug (the simulation-layer registry was still Bangalore-based after the
platform's city focus moved to Vellore) and tightens the admin database
console to an auditable, field-restricted write surface.

## 2. Scenario taxonomy

Prior to this expansion, "scenarios" were five unrelated flat presets tied
to the (now-removed) CARLA integration. They are replaced by a small
**axis-based scenario model** (`backend/app/scenario_engine.py`):

| Axis | Values | Consumed by |
|---|---|---|
| `traffic` | `normal`, `peak_surge`, `heavy_congestion` | `simulation/traci_bridge.py` (per-vehicle SUMO speed factor) |
| `weather` | `clear`, `rain`, `extreme_heat`, `fog` | `traci_bridge.py` (additional speed factor); `charging_advisor.py` |
| station availability | DB `Charger.status`/`Station.queue_length` mutation | unchanged from the original preset mechanism |
| `grid_stress` | `normal`, `feeder_overload` | `simulation/grid_sim.py` (additive non-EV background demand) |
| `fault_injection_rate` | `baseline`, `elevated` | `simulation/charger_monitor_sim.py` |

Eight named scenarios span this space (`normal`, `station_shutdown`,
`station_queued`, `station_degraded`, `high_congestion`,
`monsoon_evening_rush`, `summer_heat_grid_stress`, `fog_morning`) rather
than the full combinatorial product, each chosen to represent a distinct,
independently-justified operating condition. Activating a scenario
(`POST /simulation/scenario`) both mutates the DB (station-level effect, as
before) and broadcasts the full axis payload over MQTT on a **retained**
`scenario/active` topic, so every simulation process - including ones that
start or restart after the scenario was activated - picks up the current
state immediately, without a container restart.

The pre-existing mass-gathering stress-burst mechanism
(`simulation/event_stress_sim.py`) is kept as an orthogonal, on-demand
trigger rather than folded into this axis model - it answers a different
question (a temporary density spike at one station) than the
steady-state conditions the five axes above describe.

## 3. Weather integration and the charging-time advisory

`backend/app/services/weather_service.py` fetches real current weather for
Vellore from [Open-Meteo](https://open-meteo.com) (free, no API key - the
same "zero-cost" posture as the rest of the platform), cached for 20
minutes. On a fetch failure, the last good reading is served (marked
stale) rather than raising, so a transient weather-API outage degrades the
advisory, not the page that shows it.

`backend/app/services/charging_advisor.py` combines three independent,
individually-labeled signals into one `good`/`fair`/`poor` recommendation:

1. **Weather** - extreme heat (>=40C) flags battery thermal stress and
   reduced charging efficiency; rain/fog flag extra travel time.
2. **Grid load** - live feeder state from twin-engine (`/twin/feeder`, the
   same data the admin dashboard's Feeder Load cards show); any overloaded
   feeder, or high average loading, downgrades the recommendation.
3. **Time-of-day tariff** - a fixed 6pm-10pm IST peak-hours heuristic.

Each factor can only ever **downgrade** the level, never upgrade past what
another factor already capped it at - a single serious issue can't be
diluted by two mild positives. The rules are deliberately simple and
inspectable rather than a trained model: a recommendation a driver has to
trust and act on needs a one-sentence justification per factor, which a
rules engine provides for free and a black-box model does not.

Real weather also replaces the previously-synthetic `weather: 0/1` feature
`backend/ml/demand_forecast.py` already had a parameter for
(`GET /demand-forecast/predict` now defaults to today's real conditions
when the caller doesn't explicitly override it).

## 4. Simulated embedded fault-detection layer

### 4.1 Framing

The platform has a standing constraint (`docs/out-of-scope.md`, Section 2):
no physical hardware, simulate every output. The fault-detection layer
(`simulation/charger_monitor_sim.py`) is a **software simulation of a
Charger Monitoring Unit (CMU)** - conceptually equivalent to a low-cost
microcontroller (ESP32/STM32-class) sampling, per port: a current-sense
shunt resistor, an NTC thermistor, a voltage divider, an RCD-style
earth-leakage sense line, the IEC 61851 Control Pilot/Proximity Pilot
signal pair, and its own cellular/WiFi modem's signal strength - running a
local debounced threshold state machine. It is explicitly *not* a claim
that physical hardware exists; it is a claim that the simulated behavior
matches what real hardware would report, using real vocabularies rather
than invented ones.

### 4.2 Sensor suite

`simulation/station_sim.py` (the pre-existing per-charger SimPy queueing
model) was extended to publish a full electrical telemetry set on every
`charger/status/{id}` message, not just a status string: `voltage_v`,
`current_a`, `power_factor`, `frequency_hz`, `temperature_c` (a
load-dependent first-order thermal-lag approximation), and a running
`energy_delivered_kwh` meter - reported both on state transitions (OCPP
`StatusNotification` semantics) and periodically mid-session (OCPP
`MeterValues` semantics), matching how a real EVSE controller reports on
both channels. Nominal voltage is derived from rated power: 230V
single-phase AC for <=22kW ports, 400V/650V DC tiers above that.

### 4.3 Fault taxonomy

`charger_monitor_sim.py` watches this telemetry (it does not re-simulate
the charger's physics - matching how a real monitoring IC watches sensor
lines independent of the power-delivery hardware) and reports real **OCPP
StatusNotification ErrorCode** values, debounced (2 consecutive threshold
breaches) to avoid single-tick noise:

| Code | Trigger |
|---|---|
| `OverCurrentFailure` | current > 1.15x rated |
| `OverVoltage` / `UnderVoltage` | voltage outside +-10% of nominal (EN 50160) |
| `HighTemperature` | > 70C (DC) / 60C (AC) |
| `GroundFailure` | synthetic earth-leakage reading > 30mA (IEC 61851 RCD trip threshold) |
| `WeakSignal` | backhaul signal < 40% (site-type baseline: 90% urban DC hub, 65% highway corridor - realistically weaker at exposed sites) |
| `PowerMeterFailure` | status=occupied but sustained near-zero current |
| `ConnectorLockFailure`, `ReaderFailure`, `PowerSwitchFailure`, `InternalError` | injected-only (tamper/physical, payment-reader, contactor, and generic-electronics failure classes - no single continuous sensor backs these, matching their real-world discrete-event nature) |
| `NoError` | periodic heartbeat when healthy, so "monitored and healthy" is distinguishable from "not reporting at all" |

Fault injection rate is controlled by the scenario `fault_injection_rate`
axis (baseline ~0.0006/tick, elevated ~0.003/tick), each injected fault
persisting 60-300s before auto-clearing - independent of, and layered on
top of, whatever organic extremes real load already produces.

### 4.4 Integration with the existing trust layer

Rather than building a second, parallel risk-scoring system,
`backend/app/services/fault_consumer.py` subscribes to `charger/fault/{id}`
and feeds detected faults into the *existing*
`ml/maintenance_predictor.py` (`Section 5.11`) risk score - exactly what
`docs/security-notes.md` already anticipated a richer fault signal would
do. `ChargerTelemetryWindow` gained `critical_fault_count`/
`warning_fault_count` fields (critical faults weighted ~0.8, warnings
~0.3, additive with the existing abort/error-rate excess terms), and a
charger's `status` flips to `maintenance` once 2 critical faults land in a
2-hour rolling window - visible on `StationHealthPage.tsx`, which now
polls every 6s and shows each charger's live status alongside a
`last_verified_at` freshness indicator.

**A real data-mapping constraint**: the simulation-layer registry
(`simulation/registry.py`) and the DB-backed `stations`/`chargers` tables
are independent datasets with no shared identifier
(`docs/out-of-scope.md`). `fault_consumer.py` correlates a simulated
fault's station to a real DB station via a static coordinate lookup
(`SIMULATION_STATION_COORDS`) plus the same nearest-station matching
`scenario_engine.find_nearest_station` already uses - not a foreign key.
This is an explicit, documented limitation, not silently worked around.

### 4.5 Fault-informed capacity planning

The mass-gathering stress-test capacity planner
(`POST /stress-test/sweep`, `backend/ml/event_stress_test.py`) originally
recommended additional stations assuming every new station delivers its
full nameplate `station_capacity_kw` indefinitely. That's optimistic once
the fault-detection layer above is in the loop: a real fleet always has
some fraction of ports down for fault-driven maintenance at any given
time, and a newly built station will fail at a comparable rate once
deployed, not at 0%.

`recommend_additional_stations()` now accepts an optional
`fleet_availability_ratio` - the fraction of chargers *not* currently in
`maintenance` status - and derates each station's assumed contribution by
it before dividing into the capacity deficit. The endpoint computes this
ratio live from the DB (chargers in `maintenance` / total chargers) and
returns both the naive and the reliability-adjusted station count
side by side, rather than silently replacing one with the other -
so a planner can see exactly how much of the gap is "more capacity
needed" versus "the capacity we already have isn't reliable." The
parameter defaults to `1.0` (no derating), so every existing caller with
no fault data behaves exactly as before.

## 5. Reservation system

`POST /stations/{id}/reserve-any` (and the charger-specific
`POST /stations/chargers/{id}/reserve`) places a 10-minute hold on a port,
recording `reserved_until` and `reserved_by_user_id` on the `Charger` row.
Reservations are **lazily expired on read** rather than via a background
sweep job - nothing downstream depends on the expiry firing at the exact
moment it lapses, only on it being gone by the next time anyone looks.

A real bug surfaced and was fixed during implementation: `start-at-station`
originally only matched `status == "available"` chargers, meaning a user
who reserved a specific port could not actually claim it - the reservation
made the port invisible to everyone, including its own holder. Fixed by
having `start-at-station` prefer the caller's own active reservation before
falling back to "first available."

Station cards also show a wait-time estimate
(`queue_length * mean_session_minutes_for_station_type / charger_count`),
mirroring `station_sim.py`'s own per-type session-duration distributions
(documented as an intentional, small duplication rather than a shared
import - the simulation and backend services communicate only over MQTT).

## 6. Admin database console: RBAC tightening

The generic admin database browser/editor (`backend/app/routers/
admin_database.py`) previously allowed unrestricted create/update/delete
across every table. This was narrowed to match real production-system
practice for a console touching PII and financial/operational data:

- **No hard delete, anywhere.** A raw DELETE with no trace is itself a
  compliance concern (SOC2/ISO 27001, India's DPDP Act) independent of
  whether removing the row was legitimate. The endpoint now always returns
  403 with guidance to use a status field or the resource's own dedicated
  endpoint instead.
- **Create blocked for transactional/log tables** (`sessions`,
  `telemetry`, `battery_health`, `carbon_ledger`, `charging_behavior_log`,
  `demand_model_training_runs`) - the platform itself is the only
  legitimate writer for audit/financial history.
- **Update restricted to a per-table field allow-list**
  (`EDITABLE_FIELDS_BY_TABLE`) - e.g. a user's phone/license number, a
  station's safety score, a charger's operational status - excluding
  auth/security fields, foreign keys, and fields another automated system
  owns (`Charger.maintenance_risk_score` is fault-consumer-owned;
  `last_verified_at` is the trust layer's own signal). A table with no
  allow-list entry has nothing editable at all - safe by default.
- **Every create/update is audit-logged** (`AdminAuditLog`: who, which
  table/row, before/after, when), retrievable via `GET /admin/db/audit-log`.

## 7. Live results/evaluation endpoint

`GET /simulation/report` (`backend/app/routers/simulation.py`) aggregates
the numbers a paper's results/evaluation section actually needs into one
call, rather than requiring them to be hand-assembled from several
endpoints and a spreadsheet: current charger utilization (available vs.
occupied vs. maintenance, and the resulting utilization percentage),
estimated queue wait (derived from each station's live `queue_length` and
its station-type's mean session duration, the same formula the frontend's
wait-time badge already uses), energy delivered and session count over a
rolling 24-hour window, in-window fault-detection totals (critical/warning
counts and how many chargers currently have an active fault) from the
fault-detection layer (Section 4.4), and live feeder overload state
(feeders reporting, feeders currently overloaded, average transformer
loading) pulled from the same twin-engine state `/twin/feeder` already
serves. Every field is a real current snapshot computed from the same DB
rows and live twin state the rest of the app reads - there is deliberately
no fabricated historical field like "cumulative overload minutes," since
the platform doesn't retain a feeder-state time series to compute that
from truthfully; a future pass adding that time series (e.g. via
Prometheus, already deployed - `docs/architecture.md`) could add it later
without changing this endpoint's shape.

## 8. Reproducibility

Every sim process that uses `random` (`station_sim.py`, `swap_sim.py`,
`grid_sim.py`, `charger_monitor_sim.py`) and SUMO itself
(`traci_bridge.py`, via `--seed`) now honor a `RANDOM_SEED` environment
variable (`.env`, passed through `docker-compose.yml`). Unset (the
default) preserves genuinely random live-demo variation; set to any
integer, every process becomes reproducible run-to-run - necessary for a
paper's results to be independently re-derived to the same numbers.
`simulation/solar_sim.py` is deliberately not included - its diurnal
generation curve is a pure deterministic function with no randomness to
seed.

## 9. Stakeholder problem -> system response

Compiled from a deliberate multi-perspective pass (driver, station
controller, network operator, grid manager, grid planner) over real,
literature-grounded EV-charging-infrastructure pain points:

| Stakeholder | Problem | System response |
|---|---|---|
| Driver | "Available" can mean stale, not really free | Reported-vs-verified trust layer (Section 4.2, pre-existing) + fault-detection layer feeding it live |
| Driver | Charging speed silently worse than advertised | `PowerMeterFailure`/threshold detection surfaces this as a real fault, not silence |
| Driver | No visibility into queue wait or ability to hold a spot | Wait-time estimate + 10-minute port reservation (Section 5) |
| Driver | "Is now a good time to charge?" | Charging-time advisory (Section 3) |
| Station controller | Reactive-only maintenance, no standardized fault vocabulary | OCPP-coded fault-detection layer (Section 4), vendor-agnostic |
| Station controller | Theft/vandalism as a distinct failure class | `ConnectorLockFailure` tamper category |
| Network operator | Truck-roll cost from unnecessary site visits | Predictive maintenance risk score, now fault-informed |
| Network operator | OCPP remote-command security | `docs/security-notes.md`'s existing payload-signing design (not yet implemented - see Limitations) |
| Grid manager | Spiky, correlated EV load vs. slow-changing demand models | Per-feeder independent `pandapower` networks (pre-existing) + `grid_stress` scenario axis |
| Grid manager | Rural feeder fragility | `rural_minigrid.py` (pre-existing) + a dedicated rural-mini-grid feeder in the Vellore registry |
| Grid manager | Tariff signals not reaching drivers at decision time | Time-of-day factor folded into the charging advisory |
| Grid planner | Where/how much capacity to add | `/stress-test/sweep` mass-gathering capacity recommendation |
| Grid planner | Capacity plans assume every new station is 100% reliable | Fault-informed reliability derating (Section 4.5) |

## 10. Limitations and explicit non-goals

Stated plainly rather than silently omitted:

- **MQTT/OCPP payload signing** is designed (`docs/security-notes.md`) but
  not implemented - the fault-detection MQTT topic is unauthenticated, as
  is every other topic in the platform. A real deployment needs this.
- **Roaming/cross-network interoperability** is a business/standards
  problem between competing charging networks, not something a
  single-platform simulation can meaningfully model.
- **Grid-upgrade cost allocation and land acquisition** are policy and
  capital-planning questions outside a software simulation's scope.
- **Voltage harmonics / power-quality effects** from DC fast chargers are
  not modeled - the `pandapower` networks compute steady-state loading and
  voltage magnitude, not harmonic content.
- **Battery degradation over repeated charge cycles** is not modeled.
- The simulation-layer registry and DB-backed stations remain two
  datasets correlated by a static coordinate table, not a shared foreign
  key (Section 4.4) - full unification is real integration work for a
  future pass.
- **`docs/api-spec.yaml` documents roughly half the platform's actual
  routes** (spot-checked: ~38 documented paths against ~68 real route
  decorators across `backend/app/routers/`) - a longstanding drift that
  predates this expansion, not something introduced by it. `/simulation/report`
  and the reservation, weather, and admin-database endpoints added across
  this and earlier sessions are among the undocumented ones. Bringing the
  spec current is real, scoped work for its own pass rather than something
  to half-do alongside this one.
