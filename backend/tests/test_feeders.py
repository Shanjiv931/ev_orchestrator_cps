def test_create_and_filter_rural_minigrid_feeder(client):
    client.post("/feeders", json={
        "feeder_zone": "Test Rural Zone", "capacity_kw": 25.0, "is_rural_minigrid": True,
    })
    client.post("/feeders", json={
        "feeder_zone": "Test Urban Zone", "capacity_kw": 1000.0, "is_rural_minigrid": False,
    })

    rural = client.get("/feeders", params={"is_rural_minigrid": True})
    assert rural.status_code == 200
    assert all(f["is_rural_minigrid"] for f in rural.json())
    assert any(f["feeder_zone"] == "Test Rural Zone" for f in rural.json())


def test_update_feeder_current_load(client):
    created = client.post("/feeders", json={"feeder_zone": "Load Test Zone", "capacity_kw": 500.0})
    feeder_id = created.json()["id"]

    updated = client.patch(f"/feeders/{feeder_id}", json={"current_load_kw": 123.4})
    assert updated.status_code == 200
    assert updated.json()["current_load_kw"] == 123.4


def test_get_missing_feeder_404s(client):
    response = client.get("/feeders/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
