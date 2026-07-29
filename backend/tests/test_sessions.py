def _create_vehicle(client, headers) -> str:
    created = client.post("/vehicles", headers=headers, json={
        "vehicle_class": "4W", "connector_type": "CCS2", "battery_chemistry": "NMC", "is_pluggable": True,
    })
    return created.json()["id"]


def test_start_and_complete_session(client, auth_headers):
    headers = auth_headers("driver1@example.com")
    vehicle_id = _create_vehicle(client, headers)

    started = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id})
    assert started.status_code == 201
    session_id = started.json()["id"]
    assert started.json()["end_time"] is None

    completed = client.post(f"/sessions/{session_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["end_time"] is not None


def test_cannot_start_session_for_another_users_vehicle(client, auth_headers):
    owner_headers = auth_headers("driver2@example.com")
    other_headers = auth_headers("driver3@example.com")
    vehicle_id = _create_vehicle(client, owner_headers)

    response = client.post("/sessions", headers=other_headers, json={"vehicle_id": vehicle_id})
    assert response.status_code == 404


def test_ingest_and_list_telemetry(client, auth_headers):
    headers = auth_headers("driver4@example.com")
    vehicle_id = _create_vehicle(client, headers)
    session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]

    ingest = client.post(f"/sessions/{session_id}/telemetry", headers=headers, json={
        "battery_pct": 55.0, "cell_temp_c": 32.5, "power_kw": 45.0,
    })
    assert ingest.status_code == 201

    listed = client.get(f"/sessions/{session_id}/telemetry", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["battery_pct"] == 55.0


def test_update_session_energy_and_cost(client, auth_headers):
    headers = auth_headers("driver5@example.com")
    vehicle_id = _create_vehicle(client, headers)
    session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]

    updated = client.patch(f"/sessions/{session_id}", headers=headers, json={"energy_kwh": 12.5, "cost": 187.5})
    assert updated.status_code == 200
    assert updated.json()["energy_kwh"] == 12.5
    assert updated.json()["cost"] == 187.5
