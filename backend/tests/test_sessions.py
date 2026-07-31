def test_start_and_complete_session(client, auth_headers, create_test_vehicle):
    email = "driver1@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)

    started = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id})
    assert started.status_code == 201
    session_id = started.json()["id"]
    assert started.json()["end_time"] is None

    completed = client.post(f"/sessions/{session_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["end_time"] is not None


def test_cannot_start_session_for_another_users_vehicle(client, auth_headers, create_test_vehicle):
    owner_email = "driver2@example.com"
    owner_headers = auth_headers(owner_email)
    other_headers = auth_headers("driver3@example.com")
    vehicle_id = str(create_test_vehicle(owner_email).id)

    response = client.post("/sessions", headers=other_headers, json={"vehicle_id": vehicle_id})
    assert response.status_code == 404


def test_ingest_and_list_telemetry(client, auth_headers, create_test_vehicle):
    email = "driver4@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]

    ingest = client.post(f"/sessions/{session_id}/telemetry", headers=headers, json={
        "battery_pct": 55.0, "cell_temp_c": 32.5, "power_kw": 45.0,
    })
    assert ingest.status_code == 201

    listed = client.get(f"/sessions/{session_id}/telemetry", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["battery_pct"] == 55.0


def test_update_session_energy_and_cost(client, auth_headers, create_test_vehicle):
    email = "driver5@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]

    updated = client.patch(f"/sessions/{session_id}", headers=headers, json={"energy_kwh": 12.5, "cost": 187.5})
    assert updated.status_code == 200
    assert updated.json()["energy_kwh"] == 12.5
    assert updated.json()["cost"] == 187.5


def _create_station_with_chargers(client, count: int = 2) -> str:
    station = client.post("/stations", json={"station_type": "public_dc_hub", "lat": 12.97, "lon": 79.13})
    station_id = station.json()["id"]
    for _ in range(count):
        client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})
    return station_id


def test_start_at_station_assigns_lowest_free_port(client, auth_headers, create_test_vehicle):
    email = "driver6@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    station_id = _create_station_with_chargers(client)

    started = client.post("/sessions/start-at-station", headers=headers,
                           json={"vehicle_id": vehicle_id, "station_id": station_id})
    assert started.status_code == 201
    body = started.json()
    assert body["port_number"] is not None
    assert body["charger_id"] is not None

    station = client.get(f"/stations/{station_id}").json()
    assigned = next(c for c in station["chargers"] if c["id"] == body["charger_id"])
    assert assigned["status"] == "occupied"


def test_start_at_station_409s_when_no_charger_free(client, auth_headers, create_test_vehicle):
    email = "driver7@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    station_id = _create_station_with_chargers(client, count=1)

    first = client.post("/sessions/start-at-station", headers=headers,
                         json={"vehicle_id": vehicle_id, "station_id": station_id})
    assert first.status_code == 201

    second = client.post("/sessions/start-at-station", headers=headers,
                          json={"vehicle_id": vehicle_id, "station_id": station_id})
    assert second.status_code == 409


def test_completing_session_releases_the_charger(client, auth_headers, create_test_vehicle):
    email = "driver8@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    station_id = _create_station_with_chargers(client, count=1)

    started = client.post("/sessions/start-at-station", headers=headers,
                           json={"vehicle_id": vehicle_id, "station_id": station_id}).json()

    client.post(f"/sessions/{started['id']}/complete", headers=headers)

    station = client.get(f"/stations/{station_id}").json()
    assigned = next(c for c in station["chargers"] if c["id"] == started["charger_id"])
    assert assigned["status"] == "available"

    # a second start-at-station should now succeed against the freed charger
    retried = client.post("/sessions/start-at-station", headers=headers,
                           json={"vehicle_id": vehicle_id, "station_id": station_id})
    assert retried.status_code == 201
