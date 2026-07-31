def test_completing_a_session_with_energy_creates_a_carbon_ledger_entry(client, auth_headers, create_test_vehicle):
    email = "carbon1@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]
    client.patch(f"/sessions/{session_id}", headers=headers, json={"energy_kwh": 20.0})

    completed = client.post(f"/sessions/{session_id}/complete", headers=headers)
    assert completed.status_code == 200

    entries = client.get(f"/carbon-ledger/sessions/{session_id}", headers=headers)
    assert entries.status_code == 200
    assert len(entries.json()) == 1
    assert entries.json()[0]["co2_avoided_kg"] > 0


def test_completing_a_session_with_zero_energy_creates_no_carbon_entry(client, auth_headers, create_test_vehicle):
    email = "carbon2@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email, vehicle_class="2W", connector_type="swap-cassette", battery_chemistry="LFP").id)
    session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]

    client.post(f"/sessions/{session_id}/complete", headers=headers)

    entries = client.get(f"/carbon-ledger/sessions/{session_id}", headers=headers)
    assert entries.json() == []


def test_carbon_summary_aggregates_across_a_users_sessions(client, auth_headers, create_test_vehicle):
    email = "carbon3@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)

    for energy in (10.0, 15.0):
        session_id = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id}).json()["id"]
        client.patch(f"/sessions/{session_id}", headers=headers, json={"energy_kwh": energy})
        client.post(f"/sessions/{session_id}/complete", headers=headers)

    summary = client.get("/carbon-ledger/me/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["session_count"] == 2
    assert summary.json()["total_co2_avoided_kg"] > 0
