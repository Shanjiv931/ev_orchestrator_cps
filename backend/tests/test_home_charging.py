def test_register_home_charger_defaults_to_user_location(client, auth_headers, db_session):
    from app.models import User

    email = "homeowner1@example.com"
    headers = auth_headers(email)
    user = db_session.query(User).filter(User.email == email).first()
    user.lat, user.lon = 12.93, 79.14
    db_session.commit()

    created = client.post("/home-chargers", headers=headers, json={"label": "Garage AC", "power_kw": 7.4})
    assert created.status_code == 201
    body = created.json()
    assert body["lat"] == 12.93
    assert body["lon"] == 79.14


def test_register_home_charger_requires_location_when_none_on_file(client, auth_headers):
    headers = auth_headers("homeowner2@example.com")
    response = client.post("/home-chargers", headers=headers, json={"label": "Garage AC", "power_kw": 7.4})
    assert response.status_code == 400


def test_list_only_shows_own_home_chargers(client, auth_headers):
    mine = auth_headers("homeowner3@example.com")
    theirs = auth_headers("homeowner4@example.com")
    client.post("/home-chargers", headers=mine, json={"label": "Mine", "power_kw": 7.4, "lat": 12.9, "lon": 79.1})
    client.post("/home-chargers", headers=theirs, json={"label": "Theirs", "power_kw": 3.7, "lat": 12.9, "lon": 79.1})

    listed = client.get("/home-chargers", headers=mine)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["label"] == "Mine"


def test_start_and_complete_home_session(client, auth_headers, create_test_vehicle):
    email = "homeowner5@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    home_charger = client.post("/home-chargers", headers=headers,
                                json={"label": "Garage", "power_kw": 7.4, "lat": 12.9, "lon": 79.1}).json()

    started = client.post("/home-chargers/start-session", headers=headers,
                           json={"vehicle_id": vehicle_id, "home_charger_id": home_charger["id"]})
    assert started.status_code == 201
    session = started.json()
    assert session["home_charger_id"] == home_charger["id"]
    assert session["charger_id"] is None

    completed = client.post(f"/sessions/{session['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["end_time"] is not None


def test_cannot_start_two_sessions_on_the_same_home_charger(client, auth_headers, create_test_vehicle):
    email = "homeowner6@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    home_charger = client.post("/home-chargers", headers=headers,
                                json={"label": "Garage", "power_kw": 7.4, "lat": 12.9, "lon": 79.1}).json()

    first = client.post("/home-chargers/start-session", headers=headers,
                         json={"vehicle_id": vehicle_id, "home_charger_id": home_charger["id"]})
    assert first.status_code == 201

    second = client.post("/home-chargers/start-session", headers=headers,
                          json={"vehicle_id": vehicle_id, "home_charger_id": home_charger["id"]})
    assert second.status_code == 409


def test_cannot_delete_or_use_another_users_home_charger(client, auth_headers, create_test_vehicle):
    owner_email = "homeowner7@example.com"
    owner_headers = auth_headers(owner_email)
    other_headers = auth_headers("homeowner8@example.com")
    other_vehicle_id = str(create_test_vehicle("homeowner8@example.com").id)

    home_charger = client.post("/home-chargers", headers=owner_headers,
                                json={"label": "Garage", "power_kw": 7.4, "lat": 12.9, "lon": 79.1}).json()

    deleted = client.delete(f"/home-chargers/{home_charger['id']}", headers=other_headers)
    assert deleted.status_code == 404

    started = client.post("/home-chargers/start-session", headers=other_headers,
                           json={"vehicle_id": other_vehicle_id, "home_charger_id": home_charger["id"]})
    assert started.status_code == 404
