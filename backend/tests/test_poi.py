def test_list_pois_requires_auth(client):
    response = client.get("/poi")
    assert response.status_code == 401


def test_list_pois_returns_all_curated_spots(client, auth_headers):
    headers = auth_headers("poi-viewer@example.com")
    response = client.get("/poi", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert all("poi_type" in p and "nearby_available_chargers" in p for p in body)


def test_poi_with_no_nearby_station_reports_zero_chargers(client, auth_headers):
    headers = auth_headers("poi-viewer2@example.com")
    body = client.get("/poi", headers=headers).json()
    community_hall = next(p for p in body if p["name"] == "Sathuvachari Community Hall")
    assert community_hall["nearby_station_id"] is None
    assert community_hall["nearby_available_chargers"] == 0


def test_poi_reports_real_chargers_at_a_co_located_station(client, auth_headers, db_session):
    """CMC Hospital's POI coordinates are the same as its station seed
    (see app/poi_data.py) - db_session's per-test TRUNCATE wipes whatever
    seed_stations_if_empty populated at app startup, so this seeds its own
    station at that exact site rather than relying on cross-test state."""
    station = client.post("/stations", json={
        "station_type": "public_dc_hub", "lat": 12.9186, "lon": 79.1354,
    })
    station_id = station.json()["id"]
    client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})

    headers = auth_headers("poi-viewer3@example.com")
    body = client.get("/poi", headers=headers).json()
    hospital = next(p for p in body if p["name"] == "CMC Hospital - Ida Scudder Road")
    assert hospital["nearby_station_id"] == station_id
    assert hospital["nearby_available_chargers"] == 1
