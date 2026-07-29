def test_create_and_list_own_vehicle(client, auth_headers):
    headers = auth_headers("owner1@example.com")
    create = client.post("/vehicles", headers=headers, json={
        "vehicle_class": "4W", "connector_type": "CCS2", "battery_chemistry": "NMC", "is_pluggable": True,
    })
    assert create.status_code == 201
    vehicle_id = create.json()["id"]

    listed = client.get("/vehicles", headers=headers)
    assert listed.status_code == 200
    assert any(v["id"] == vehicle_id for v in listed.json())


def test_cannot_see_another_users_vehicle(client, auth_headers):
    owner_headers = auth_headers("owner2@example.com")
    other_headers = auth_headers("stranger@example.com")

    created = client.post("/vehicles", headers=owner_headers, json={
        "vehicle_class": "2W", "connector_type": "swap-cassette", "battery_chemistry": "LFP", "is_pluggable": False,
    })
    vehicle_id = created.json()["id"]

    response = client.get(f"/vehicles/{vehicle_id}", headers=other_headers)
    assert response.status_code == 404


def test_update_vehicle_connector(client, auth_headers):
    headers = auth_headers("owner3@example.com")
    created = client.post("/vehicles", headers=headers, json={
        "vehicle_class": "3W", "connector_type": "Bharat AC-001", "battery_chemistry": "lead-acid", "is_pluggable": True,
    })
    vehicle_id = created.json()["id"]

    updated = client.patch(f"/vehicles/{vehicle_id}", headers=headers, json={"connector_type": "swap-cassette"})
    assert updated.status_code == 200
    assert updated.json()["connector_type"] == "swap-cassette"


def test_delete_vehicle(client, auth_headers):
    headers = auth_headers("owner4@example.com")
    created = client.post("/vehicles", headers=headers, json={
        "vehicle_class": "4W", "connector_type": "Type 2", "battery_chemistry": "NMC", "is_pluggable": True,
    })
    vehicle_id = created.json()["id"]

    deleted = client.delete(f"/vehicles/{vehicle_id}", headers=headers)
    assert deleted.status_code == 204

    fetched = client.get(f"/vehicles/{vehicle_id}", headers=headers)
    assert fetched.status_code == 404
