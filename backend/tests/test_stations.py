def test_create_station_with_charger_and_swap_slot(client):
    station = client.post("/stations", json={
        "station_type": "public_dc_hub", "lat": 12.93, "lon": 77.62, "safety_score": 0.8, "has_solar": False,
    })
    assert station.status_code == 201
    station_id = station.json()["id"]

    charger = client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})
    assert charger.status_code == 201
    assert charger.json()["status"] == "available"

    swap_slot = client.post(f"/stations/{station_id}/swap-slots", json={"batteries_available": 12})
    assert swap_slot.status_code == 201

    fetched = client.get(f"/stations/{station_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert len(body["chargers"]) == 1
    assert len(body["swap_slots"]) == 1
    assert body["swap_slots"][0]["batteries_available"] == 12


def test_filter_stations_by_type(client):
    client.post("/stations", json={"station_type": "housing_society_ac", "lat": 12.9, "lon": 77.6})
    client.post("/stations", json={"station_type": "highway_corridor", "lat": 13.0, "lon": 77.4})

    filtered = client.get("/stations", params={"station_type": "highway_corridor"})
    assert filtered.status_code == 200
    assert all(s["station_type"] == "highway_corridor" for s in filtered.json())
    assert len(filtered.json()) >= 1


def test_charger_status_updates_persist(client):
    station = client.post("/stations", json={"station_type": "public_dc_hub", "lat": 12.9, "lon": 77.6})
    station_id = station.json()["id"]
    charger = client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})
    charger_id = charger.json()["id"]

    updated = client.patch(f"/stations/chargers/{charger_id}", json={"status": "occupied"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "occupied"


def test_get_missing_station_404s(client):
    response = client.get("/stations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
