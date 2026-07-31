def _create_vehicle_and_session(client, create_test_vehicle, email, headers) -> str:
    vehicle_id = str(create_test_vehicle(email).id)
    session = client.post("/sessions", headers=headers, json={"vehicle_id": vehicle_id})
    return session.json()["id"]


def test_initiate_and_confirm_payment_for_own_session(client, auth_headers, create_test_vehicle):
    email = "payer1@example.com"
    headers = auth_headers(email)
    session_id = _create_vehicle_and_session(client, create_test_vehicle, email, headers)

    initiated = client.post(f"/payments/sessions/{session_id}/initiate", headers=headers)
    assert initiated.status_code == 200
    body = initiated.json()
    assert "SIMULATED" in body["note"].upper()
    reference = body["reference"]

    confirmed = client.post(f"/payments/{reference}/confirm", headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"


def test_cannot_initiate_payment_for_another_users_session(client, auth_headers, create_test_vehicle):
    owner_email = "payer2@example.com"
    owner_headers = auth_headers(owner_email)
    other_headers = auth_headers("payer3@example.com")
    session_id = _create_vehicle_and_session(client, create_test_vehicle, owner_email, owner_headers)

    response = client.post(f"/payments/sessions/{session_id}/initiate", headers=other_headers)
    assert response.status_code == 404


def test_confirm_unknown_reference_404s(client, auth_headers):
    headers = auth_headers("payer4@example.com")
    response = client.post("/payments/SIM-NOT-REAL/confirm", headers=headers)
    assert response.status_code == 404
