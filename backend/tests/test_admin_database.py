from app.auth import create_access_token, hash_password
from app.models import User


def _make_admin_headers(db_session, email: str) -> dict:
    user = User(
        name="Admin", email=email, hashed_password=hash_password("adminpass123"),
        persona="city_admin", dpdp_consent_flag=True, email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(user.id, user.persona)
    return {"Authorization": f"Bearer {token}"}


def test_list_tables_requires_admin(client, auth_headers):
    headers = auth_headers("not-admin@example.com")
    response = client.get("/admin/db/tables", headers=headers)
    assert response.status_code == 403


def test_list_tables_requires_auth(client):
    response = client.get("/admin/db/tables")
    assert response.status_code == 401


def test_list_tables_includes_every_model_table(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin1@example.com")
    response = client.get("/admin/db/tables", headers=headers)
    assert response.status_code == 200
    names = {t["name"] for t in response.json()}
    assert {"users", "vehicles", "stations", "chargers", "sessions", "admin_audit_log"} <= names
    users_table = next(t for t in response.json() if t["name"] == "users")
    column_names = {c["name"] for c in users_table["columns"]}
    assert {"id", "email", "hashed_password", "persona"} <= column_names


def test_list_tables_reports_creatable_and_editable_metadata(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin-meta@example.com")
    tables = {t["name"]: t for t in client.get("/admin/db/tables", headers=headers).json()}

    # Transactional/log tables: not creatable through the console.
    assert tables["sessions"]["creatable"] is False
    assert tables["telemetry"]["creatable"] is False

    # Reference tables: creatable, with a non-empty (and safely scoped) editable-field list.
    assert tables["stations"]["creatable"] is True
    assert set(tables["stations"]["editable_fields"]) == {"station_type", "safety_score", "has_solar", "city", "lat", "lon"}
    assert "maintenance_risk_score" not in tables["chargers"]["editable_fields"]
    assert "last_verified_at" not in tables["chargers"]["editable_fields"]
    assert "hashed_password" not in tables["users"]["editable_fields"]
    assert "persona" not in tables["users"]["editable_fields"]

    # No table is ever deletable through this console.
    assert all(t["deletable"] is False for t in tables.values())


def test_list_rows_unknown_table_404s(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin2@example.com")
    response = client.get("/admin/db/tables/not_a_real_table/rows", headers=headers)
    assert response.status_code == 404


def test_list_rows_returns_paginated_data(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin3@example.com")
    response = client.get("/admin/db/tables/stations/rows?limit=1", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert "total" in body
    assert len(body["rows"]) <= 1


def test_create_and_update_allowed_field_on_grid_feeders(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin4@example.com")

    created = client.post("/admin/db/tables/grid_feeders/rows", headers=headers, json={
        "feeder_zone": "crud_test_zone", "capacity_kw": 100.0, "current_load_kw": 10.0, "is_rural_minigrid": False,
    })
    assert created.status_code == 201
    row_id = created.json()["id"]
    assert created.json()["feeder_zone"] == "crud_test_zone"

    # capacity_kw is on the editable allow-list for grid_feeders.
    updated = client.patch(f"/admin/db/tables/grid_feeders/rows/{row_id}", headers=headers, json={
        "capacity_kw": 250.0,
    })
    assert updated.status_code == 200
    assert updated.json()["capacity_kw"] == 250.0

    listed = client.get("/admin/db/tables/grid_feeders/rows", headers=headers)
    assert any(r["id"] == row_id for r in listed.json()["rows"])


def test_update_rejects_field_not_on_allow_list(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin-restrict@example.com")
    created = client.post("/admin/db/tables/grid_feeders/rows", headers=headers, json={
        "feeder_zone": "restricted_test", "capacity_kw": 100.0, "current_load_kw": 0.0, "is_rural_minigrid": False,
    })
    row_id = created.json()["id"]

    # current_load_kw is live-telemetry-driven, not on the allow-list.
    response = client.patch(f"/admin/db/tables/grid_feeders/rows/{row_id}", headers=headers, json={
        "current_load_kw": 999.0,
    })
    assert response.status_code == 403


def test_update_rejects_all_fields_on_tables_with_no_allow_list(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin-noedit@example.com")
    created = client.post("/admin/db/tables/meridiangrid_provisioning/rows", headers=headers, json={
        "meridiangrid_id": "MG-TEST-001", "vehicle_class": "4W", "connector_type": "CCS2",
        "battery_chemistry": "NMC", "is_pluggable": True, "brand": "Test", "vehicle_model": "Model",
        "battery_capacity_kwh": 40.0, "color_hex": "#000000", "is_claimed": False,
    })
    assert created.status_code == 201
    row_id = created.json()["id"]

    response = client.patch(f"/admin/db/tables/meridiangrid_provisioning/rows/{row_id}", headers=headers, json={
        "is_claimed": True,
    })
    assert response.status_code == 403


def test_create_row_rejects_unknown_column(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin5@example.com")
    response = client.post("/admin/db/tables/grid_feeders/rows", headers=headers, json={
        "feeder_zone": "z", "capacity_kw": 1.0, "not_a_real_column": "x",
    })
    assert response.status_code == 400


def test_create_row_rejects_duplicate_unique_value(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin6@example.com")
    payload = {
        "name": "Dup", "email": "dup-via-db@example.com", "hashed_password": "x",
        "persona": "individual_driver", "dpdp_consent_flag": False, "email_verified": True,
    }
    first = client.post("/admin/db/tables/users/rows", headers=headers, json=payload)
    assert first.status_code == 201
    second = client.post("/admin/db/tables/users/rows", headers=headers, json=payload)
    assert second.status_code == 409


def test_create_row_blocked_for_transactional_tables(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin-txn@example.com")
    response = client.post("/admin/db/tables/telemetry/rows", headers=headers, json={
        "session_id": "00000000-0000-0000-0000-000000000000", "battery_pct": 50.0,
        "cell_temp_c": 30.0, "power_kw": 10.0,
    })
    assert response.status_code == 403


def test_delete_is_always_blocked(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin7@example.com")

    station = client.post("/admin/db/tables/stations/rows", headers=headers, json={
        "station_type": "public_dc_hub", "lat": 12.9, "lon": 79.1, "safety_score": 0.5, "has_solar": False,
    })
    station_id = station.json()["id"]

    response = client.delete(f"/admin/db/tables/stations/rows/{station_id}", headers=headers)
    assert response.status_code == 403

    # still there afterwards
    fetched = client.get("/admin/db/tables/stations/rows", headers=headers)
    assert any(r["id"] == station_id for r in fetched.json()["rows"])


def test_create_and_update_are_recorded_in_audit_log(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin-audit@example.com")

    created = client.post("/admin/db/tables/stations/rows", headers=headers, json={
        "station_type": "public_dc_hub", "lat": 12.8, "lon": 79.2, "safety_score": 0.6, "has_solar": False,
    })
    station_id = created.json()["id"]
    client.patch(f"/admin/db/tables/stations/rows/{station_id}", headers=headers, json={"safety_score": 0.9})

    log = client.get("/admin/db/audit-log", headers=headers, params={"table_name": "stations"})
    assert log.status_code == 200
    entries = [e for e in log.json()["entries"] if e["row_id"] == station_id]
    actions = {e["action"] for e in entries}
    assert actions == {"create", "update"}
    update_entry = next(e for e in entries if e["action"] == "update")
    assert update_entry["before"]["safety_score"] == 0.6
    assert update_entry["after"]["safety_score"] == 0.9
