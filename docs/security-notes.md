# Security notes

## MQTT/OCPP message signing (Section 4.7)

**Threat model.** Every ranking, trust-layer penalty, grid-load reading,
and safety decision in this platform ultimately traces back to a message
published on Mosquitto by a charger, a vehicle OBU, or a swap kiosk. In
the simulator, every publisher is trusted code we wrote. In a real
deployment, every one of those publishers is a device physically
installed in an uncontrolled, sometimes unattended location (a street DC
hub, a housing-society AC point) - and MQTT and OCPP, on their own,
authenticate the *connection*, not the *payload*. A compromised or
counterfeit charger can publish `status: available` forever, or a
vehicle OBU can lie about its SoC to manipulate V2G payouts, without
breaking TLS or MQTT auth. This is telemetry spoofing, and the platform's
entire reported-vs-verified trust layer (Section 4.2) exists to be robust
against it - so the messages that feed it need to be genuinely
attributable to a real device, not merely delivered over an encrypted
channel.

**Design (concrete enough to implement without rethinking, not built
against the simulator - Section 4.7 explicitly scopes it this way):**

1. **Per-device identity, not shared credentials.** Every charger,
   vehicle OBU, and swap kiosk is provisioned with its own Ed25519
   keypair at manufacture/installation time (Ed25519: small keys and
   signatures, fast verification, no license fees - fits the zero-cost
   constraint and is well-supported in every language OCPP/MQTT stacks
   are written in). The private key never leaves the device's secure
   element; the public key is registered against the device's ID in a
   `device_public_keys` table the backend owns (a straightforward
   extension of the existing `Charger`/`Vehicle`/`SwapSlot` tables, not a
   new subsystem).

2. **Payload-level signatures, independent of transport security.** Each
   MQTT publish carries a signature over a canonical serialization of the
   payload (sorted-keys JSON, or a fixed binary layout for OCPP) plus a
   monotonic per-device sequence number and a timestamp, e.g.:
   ```json
   {
     "charger_id": "station-vit-dc-01-charger-0",
     "status": "available",
     "power_kw": 60.0,
     "seq": 4821,
     "ts": 1785300000,
     "sig": "base64(Ed25519(private_key, canonical_json(payload_without_sig)))"
   }
   ```
   `twin-engine` (the single point that already ingests every MQTT
   message today, per `twin_service.py`) verifies `sig` against the
   device's registered public key *before* writing to Redis. This is
   deliberately at the application layer, not just relying on TLS/mTLS at
   the broker: a compromised broker or a MITM at the TLS termination
   point still can't forge a valid signature without the device's private
   key, giving defense in depth beyond transport security alone.

3. **Replay protection.** The `seq` counter (persisted per device
   alongside its public key) rejects any message with `seq` <= the last
   accepted value; `ts` outside a small tolerance window (a real
   deployment: NTP-synced devices, a `±60s` window) is rejected even with
   a valid signature and an unused `seq`, closing the window for a
   captured-and-replayed message to be reissued later.

4. **OCPP-specific layering.** For the charger-to-backend OCPP channel
   specifically (distinct from the simulated MQTT telemetry bus), OCPP
   2.0.1 Security Profile 3 (mutual TLS with client certificates per
   charger) is the standard baseline and should be used as-is - it's
   already a mature, zero-cost-to-adopt spec requirement, not something
   this platform needs to reinvent. The Ed25519 payload signing above is
   additive to it, not a replacement: Security Profile 3 authenticates
   the OCPP *session*; payload signing authenticates each individual
   *message*, which matters because a single compromised session (a
   charger with a stolen certificate) shouldn't be able to spoof
   telemetry indistinguishably from every other charger on the same
   backend.

5. **Key rotation and revocation.** Device keys rotate on a fixed schedule
   (e.g. annually) or immediately on suspected compromise, via a
   `revoked_at` column on `device_public_keys` rather than deleting the
   row - twin-engine checks `revoked_at IS NULL` in addition to signature
   validity, so a revoked device's *old* signed messages already ingested
   remain auditable while new ones are rejected.

6. **Where this plugs into what's already built.** A message that fails
   signature/replay verification is exactly the kind of signal
   `maintenance_predictor.py`'s risk scoring and the reported-vs-verified
   trust layer are built to consume - a device that starts failing
   verification (not just going offline) is a stronger "investigate this
   charger" signal than a normal offline transition, and the existing
   `Charger.maintenance_risk_score` column is where that signal would
   land without any schema change.

## DPDP data retention (Section 4.7)

Every `User` carries `dpdp_consent_flag` and `consent_expiry`
(`backend/app/models/entities.py`). The retention limit is enforced by a
real, tested job - `backend/app/services/retention_job.py` - not just
documented intent:

- `find_expired_users` selects every user whose `consent_expiry` has
  passed.
- `erase_user` cascades a real delete across every table that references
  that user, in FK-safe order: `Telemetry` and `CarbonLedgerEntry` (via
  their session), `ChargingSession`, `BatteryHealth` (via their vehicle),
  `Vehicle`, then the `User` row itself.
- `run_retention_sweep` is callable directly (`python -m
  app.services.retention_job`, suitable for a cron job or a Kubernetes
  CronJob in a real deployment) and is also admin-triggerable via `POST
  /admin/dpdp-retention-sweep` for on-demand runs and testability.
- Tested end-to-end in `backend/tests/test_retention_job.py`: a fully
  populated user (vehicle, session, telemetry, battery health, carbon
  ledger entry) past their consent expiry is completely erased; a user
  with a future expiry or no expiry set is left untouched.

## Zero telemetry, by design

No analytics SDK, crash reporter, or third-party tracking script exists
anywhere in this stack (grep the repo: none of `frontend-web`,
`backend`, `twin-engine`, or `simulation` import one). The only metrics
collected are the Prometheus/Grafana observability stack described in
`docs/architecture.md#observability`, which is self-hosted, stays inside
the `docker compose` network, and is never sent to any external party.
