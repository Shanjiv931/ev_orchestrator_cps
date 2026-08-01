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
    assert {"users", "vehicles", "stations", "chargers", "sessions"} <= names
    users_table = next(t for t in response.json() if t["name"] == "users")
    column_names = {c["name"] for c in users_table["columns"]}
    assert {"id", "email", "hashed_password", "persona"} <= column_names


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


def test_full_crud_cycle_on_grid_feeders(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin4@example.com")

    created = client.post("/admin/db/tables/grid_feeders/rows", headers=headers, json={
        "feeder_zone": "crud_test_zone", "capacity_kw": 100.0, "current_load_kw": 10.0, "is_rural_minigrid": False,
    })
    assert created.status_code == 201
    row_id = created.json()["id"]
    assert created.json()["feeder_zone"] == "crud_test_zone"

    updated = client.patch(f"/admin/db/tables/grid_feeders/rows/{row_id}", headers=headers, json={
        "current_load_kw": 55.5,
    })
    assert updated.status_code == 200
    assert updated.json()["current_load_kw"] == 55.5

    listed = client.get("/admin/db/tables/grid_feeders/rows", headers=headers)
    assert any(r["id"] == row_id for r in listed.json()["rows"])

    deleted = client.delete(f"/admin/db/tables/grid_feeders/rows/{row_id}", headers=headers)
    assert deleted.status_code == 204

    deleted_again = client.delete(f"/admin/db/tables/grid_feeders/rows/{row_id}", headers=headers)
    assert deleted_again.status_code == 404


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


def test_delete_blocked_by_foreign_key_returns_409(client, db_session):
    headers = _make_admin_headers(db_session, "dbadmin7@example.com")

    station = client.post("/admin/db/tables/stations/rows", headers=headers, json={
        "station_type": "public_dc_hub", "lat": 12.9, "lon": 79.1, "safety_score": 0.5, "has_solar": False,
    })
    station_id = station.json()["id"]
    client.post("/admin/db/tables/chargers/rows", headers=headers, json={
        "station_id": station_id, "status": "available", "power_kw": 60.0, "maintenance_risk_score": 0.0,
    })

    response = client.delete(f"/admin/db/tables/stations/rows/{station_id}", headers=headers)
    assert response.status_code == 409
