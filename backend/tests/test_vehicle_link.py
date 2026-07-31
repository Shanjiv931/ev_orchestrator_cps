def test_pairing_flow_rejects_wrong_code_then_accepts_correct_one(client, auth_headers, create_test_vehicle):
    email = "pair-test@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)

    started = client.post(f"/vehicles/{vehicle_id}/pair", headers=headers)
    assert started.status_code == 200
    code = started.json()["pairing_code"]

    wrong = client.post(f"/vehicles/{vehicle_id}/pair/confirm", headers=headers, params={"code": "WRONG1"})
    assert wrong.status_code == 400

    confirmed = client.post(f"/vehicles/{vehicle_id}/pair/confirm", headers=headers, params={"code": code})
    assert confirmed.status_code == 200


def test_live_telemetry_requires_pairing_first(client, auth_headers, create_test_vehicle):
    email = "telemetry-test@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    response = client.get(f"/vehicles/{vehicle_id}/live-telemetry", headers=headers)
    assert response.status_code == 400


def test_live_telemetry_after_pairing_is_flagged_simulated(client, auth_headers, create_test_vehicle):
    email = "telemetry-test2@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    code = client.post(f"/vehicles/{vehicle_id}/pair", headers=headers).json()["pairing_code"]
    client.post(f"/vehicles/{vehicle_id}/pair/confirm", headers=headers, params={"code": code})

    telemetry = client.get(f"/vehicles/{vehicle_id}/live-telemetry", headers=headers)
    assert telemetry.status_code == 200
    body = telemetry.json()
    assert body["is_simulated"] is True
    assert 0 <= body["battery_pct"] <= 100
    assert body["range_km"] > 0


def test_cannot_pair_another_users_vehicle(client, auth_headers, create_test_vehicle):
    owner_email = "vehicle-owner@example.com"
    owner_headers = auth_headers(owner_email)
    other_headers = auth_headers("not-owner@example.com")
    vehicle_id = str(create_test_vehicle(owner_email).id)

    response = client.post(f"/vehicles/{vehicle_id}/pair", headers=other_headers)
    assert response.status_code == 404
