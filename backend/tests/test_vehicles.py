from app.auth import create_access_token, hash_password
from app.models import MeridianGridProvisioning, User


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


def _seed_provisioning(db_session, meridiangrid_id: str = "MG-TEST-0001") -> MeridianGridProvisioning:
    provisioning = MeridianGridProvisioning(
        meridiangrid_id=meridiangrid_id, vehicle_class="4W", connector_type="CCS2",
        battery_chemistry="NMC", is_pluggable=True, brand="Tata", vehicle_model="Nexon EV Long Range",
        battery_capacity_kwh=40.5, color_hex="#1D4ED8",
    )
    db_session.add(provisioning)
    db_session.commit()
    db_session.refresh(provisioning)
    return provisioning


def test_lookup_unknown_meridiangrid_id_404s(client, auth_headers):
    headers = auth_headers("lookup1@example.com")
    response = client.get("/vehicles/lookup/MG-NOPE-0000", headers=headers)
    assert response.status_code == 404


def test_lookup_returns_full_spec(client, auth_headers, db_session):
    headers = auth_headers("lookup2@example.com")
    _seed_provisioning(db_session, "MG-TEST-0002")

    response = client.get("/vehicles/lookup/MG-TEST-0002", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["brand"] == "Tata"
    assert body["battery_capacity_kwh"] == 40.5


def test_request_add_rejects_non_vellore_plate(client, auth_headers, db_session):
    headers = auth_headers("adder1@example.com")
    _seed_provisioning(db_session, "MG-TEST-0003")

    response = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-TEST-0003", "number_plate": "KA01AB1234",
    })
    assert response.status_code == 400


def test_request_add_unknown_id_404s(client, auth_headers):
    headers = auth_headers("adder2@example.com")
    response = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-GHOST-9999", "number_plate": "TN23AB1234",
    })
    assert response.status_code == 404


def test_add_request_stays_pending_and_creates_no_vehicle_until_approved(client, auth_headers, db_session):
    headers = auth_headers("adder3@example.com")
    _seed_provisioning(db_session, "MG-TEST-0004")

    requested = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-TEST-0004", "number_plate": "TN23AB1234",
    })
    assert requested.status_code == 201
    body = requested.json()
    assert body["status"] == "pending"
    assert body["ticket_code"].startswith("VG-")

    assert client.get("/vehicles", headers=headers).json() == []

    tracked = client.get(f"/vehicles/requests/track/{body['ticket_code']}", headers=headers)
    assert tracked.status_code == 200
    assert tracked.json()["status"] == "pending"


def test_admin_approving_add_request_creates_vehicle_and_claims_id(client, auth_headers, db_session):
    email = "adder4@example.com"
    headers = auth_headers(email)
    admin_headers = _make_admin_headers(db_session, "vehicle-admin1@example.com")
    _seed_provisioning(db_session, "MG-TEST-0005")

    ticket = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-TEST-0005", "number_plate": "TN23AB1234",
    }).json()

    approved = client.post(f"/admin/vehicle-requests/{ticket['id']}/approve", headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    vehicles = client.get("/vehicles", headers=headers).json()
    assert len(vehicles) == 1
    assert vehicles[0]["brand"] == "Tata"
    assert vehicles[0]["number_plate"] == "TN23AB1234"

    # the ID can never be claimed a second time
    dupe = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-TEST-0005", "number_plate": "TN23CD5678",
    })
    assert dupe.status_code == 409


def test_admin_rejecting_add_request_creates_no_vehicle(client, auth_headers, db_session):
    email = "adder5@example.com"
    headers = auth_headers(email)
    admin_headers = _make_admin_headers(db_session, "vehicle-admin2@example.com")
    _seed_provisioning(db_session, "MG-TEST-0006")

    ticket = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-TEST-0006", "number_plate": "TN23AB1234",
    }).json()

    rejected = client.post(f"/admin/vehicle-requests/{ticket['id']}/reject", headers=admin_headers,
                            json={"admin_notes": "plate could not be verified"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get("/vehicles", headers=headers).json() == []


def test_non_admin_cannot_approve_vehicle_requests(client, auth_headers, db_session):
    email = "adder6@example.com"
    headers = auth_headers(email)
    _seed_provisioning(db_session, "MG-TEST-0007")
    ticket = client.post("/vehicles/requests/add", headers=headers, json={
        "meridiangrid_id": "MG-TEST-0007", "number_plate": "TN23AB1234",
    }).json()

    response = client.post(f"/admin/vehicle-requests/{ticket['id']}/approve", headers=headers)
    assert response.status_code == 403


def test_delete_request_requires_known_reason_code(client, auth_headers, create_test_vehicle):
    email = "deleter1@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)

    response = client.post("/vehicles/requests/delete", headers=headers, json={
        "vehicle_id": vehicle_id, "reason_code": "not_a_real_reason",
    })
    assert response.status_code == 400


def test_delete_request_other_reason_requires_detail(client, auth_headers, create_test_vehicle):
    email = "deleter2@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)

    response = client.post("/vehicles/requests/delete", headers=headers, json={
        "vehicle_id": vehicle_id, "reason_code": "other",
    })
    assert response.status_code == 400


def test_admin_approving_delete_request_removes_vehicle(client, auth_headers, create_test_vehicle, db_session):
    email = "deleter3@example.com"
    headers = auth_headers(email)
    admin_headers = _make_admin_headers(db_session, "vehicle-admin3@example.com")
    vehicle_id = str(create_test_vehicle(email).id)

    ticket = client.post("/vehicles/requests/delete", headers=headers, json={
        "vehicle_id": vehicle_id, "reason_code": "sold_or_transferred",
    }).json()
    assert ticket["status"] == "pending"

    approved = client.post(f"/admin/vehicle-requests/{ticket['id']}/approve", headers=admin_headers)
    assert approved.status_code == 200

    fetched = client.get(f"/vehicles/{vehicle_id}", headers=headers)
    assert fetched.status_code == 404


def test_cannot_request_deletion_of_another_users_vehicle(client, auth_headers, create_test_vehicle):
    owner_email = "deleter4@example.com"
    owner_headers = auth_headers(owner_email)
    other_headers = auth_headers("deleter5@example.com")
    vehicle_id = str(create_test_vehicle(owner_email).id)

    response = client.post("/vehicles/requests/delete", headers=other_headers, json={
        "vehicle_id": vehicle_id, "reason_code": "sold_or_transferred",
    })
    assert response.status_code == 404
