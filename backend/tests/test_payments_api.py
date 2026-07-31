def _create_vehicle_and_session(client, create_test_vehicle, email, headers) -> str:
    vehicle_id = str(create_test_vehicle(email).id)
    session = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id})
    return session.json()["id"]


def test_get_session_payment_shows_unpaid_by_default(client, auth_headers, create_test_vehicle):
    email = "payer1@example.com"
    headers = auth_headers(email)
    session_id = _create_vehicle_and_session(client, create_test_vehicle, email, headers)

    payment = client.get(f"/payments/sessions/{session_id}", headers=headers)
    assert payment.status_code == 200
    body = payment.json()
    assert body["payment_status"] == "unpaid"
    assert body["payment_method"] is None


def test_pay_for_session_marks_it_paid(client, auth_headers, create_test_vehicle):
    email = "payer2@example.com"
    headers = auth_headers(email)
    session_id = _create_vehicle_and_session(client, create_test_vehicle, email, headers)

    paid = client.post(f"/payments/sessions/{session_id}/pay", headers=headers, json={"method": "upi"})
    assert paid.status_code == 200
    body = paid.json()
    assert body["payment_status"] == "paid"
    assert body["payment_method"] == "upi"
    assert body["paid_at"] is not None


def test_cannot_pay_twice(client, auth_headers, create_test_vehicle):
    email = "payer3@example.com"
    headers = auth_headers(email)
    session_id = _create_vehicle_and_session(client, create_test_vehicle, email, headers)

    client.post(f"/payments/sessions/{session_id}/pay", headers=headers, json={"method": "cash"})
    second = client.post(f"/payments/sessions/{session_id}/pay", headers=headers, json={"method": "card"})
    assert second.status_code == 409


def test_pay_rejects_unknown_method(client, auth_headers, create_test_vehicle):
    email = "payer4@example.com"
    headers = auth_headers(email)
    session_id = _create_vehicle_and_session(client, create_test_vehicle, email, headers)

    response = client.post(f"/payments/sessions/{session_id}/pay", headers=headers, json={"method": "bitcoin"})
    assert response.status_code == 400


def test_cannot_pay_for_another_users_session(client, auth_headers, create_test_vehicle):
    owner_email = "payer5@example.com"
    owner_headers = auth_headers(owner_email)
    other_headers = auth_headers("payer6@example.com")
    session_id = _create_vehicle_and_session(client, create_test_vehicle, owner_email, owner_headers)

    response = client.post(f"/payments/sessions/{session_id}/pay", headers=other_headers, json={"method": "cash"})
    assert response.status_code == 404


def test_payment_includes_station_when_charger_assigned(client, auth_headers, create_test_vehicle):
    email = "payer7@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)

    station = client.post("/stations", json={"station_type": "public_dc_hub", "lat": 12.97, "lon": 79.13})
    station_id = station.json()["id"]
    client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})

    started = client.post("/sessions/start-at-station", headers=headers,
                           json={"vehicle_id": vehicle_id, "station_id": station_id}).json()

    payment = client.get(f"/payments/sessions/{started['id']}", headers=headers)
    assert payment.status_code == 200
    body = payment.json()
    assert body["station_id"] == station_id
    assert body["station_name"] == "public_dc_hub"
