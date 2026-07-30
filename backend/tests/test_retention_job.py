import uuid
from datetime import datetime, timedelta, timezone

from app.models import BatteryHealth, CarbonLedgerEntry, ChargingSession, Telemetry, User, Vehicle
from app.services.retention_job import find_expired_users, run_retention_sweep


def _make_user(db_session, consent_expiry=None) -> User:
    user = User(
        name="Retention Test", email=f"{uuid.uuid4().hex}@example.com", hashed_password="x",
        persona="individual_driver", consent_expiry=consent_expiry,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _fully_populate(db_session, user: User) -> ChargingSession:
    vehicle = Vehicle(user_id=user.id, vehicle_class="4W", connector_type="CCS2",
                       battery_chemistry="NMC", is_pluggable=True)
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    db_session.add(BatteryHealth(vehicle_id=vehicle.id, soh_pct=90.0))

    session = ChargingSession(user_id=user.id, vehicle_id=vehicle.id, energy_kwh=10.0, cost=150.0)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    db_session.add(Telemetry(session_id=session.id, battery_pct=50.0, cell_temp_c=30.0, power_kw=20.0))
    db_session.add(CarbonLedgerEntry(session_id=session.id, co2_avoided_kg=2.5, equivalent_fuel_baseline="petrol 4W"))
    db_session.commit()
    return session


def test_finds_only_users_with_expired_consent(db_session):
    now = datetime.now(timezone.utc)
    expired = _make_user(db_session, consent_expiry=now - timedelta(days=1))
    not_expired = _make_user(db_session, consent_expiry=now + timedelta(days=30))
    no_expiry = _make_user(db_session, consent_expiry=None)

    found_ids = {u.id for u in find_expired_users(db_session, now=now)}
    assert expired.id in found_ids
    assert not_expired.id not in found_ids
    assert no_expiry.id not in found_ids


def test_sweep_erases_expired_user_and_all_dependent_rows(db_session):
    now = datetime.now(timezone.utc)
    user = _make_user(db_session, consent_expiry=now - timedelta(days=1))
    session = _fully_populate(db_session, user)
    user_id, vehicle_id, session_id = user.id, session.vehicle_id, session.id

    erased_count = run_retention_sweep(db_session, now=now)
    assert erased_count == 1

    assert db_session.get(User, user_id) is None
    assert db_session.get(Vehicle, vehicle_id) is None
    assert db_session.get(ChargingSession, session_id) is None
    assert db_session.query(Telemetry).filter(Telemetry.session_id == session_id).count() == 0
    assert db_session.query(CarbonLedgerEntry).filter(CarbonLedgerEntry.session_id == session_id).count() == 0
    assert db_session.query(BatteryHealth).filter(BatteryHealth.vehicle_id == vehicle_id).count() == 0


def test_sweep_leaves_users_with_unexpired_or_no_consent_untouched(db_session):
    now = datetime.now(timezone.utc)
    safe_user = _make_user(db_session, consent_expiry=now + timedelta(days=30))
    no_expiry_user = _make_user(db_session, consent_expiry=None)

    erased_count = run_retention_sweep(db_session, now=now)
    assert erased_count == 0
    assert db_session.get(User, safe_user.id) is not None
    assert db_session.get(User, no_expiry_user.id) is not None


def test_sweep_via_api_endpoint(client, auth_headers):
    """The retention job must be admin-triggerable, not just a bare script."""
    headers = auth_headers("retention-admin@example.com")
    response = client.post("/admin/dpdp-retention-sweep", headers=headers)
    assert response.status_code == 200
    assert "users_erased" in response.json()
