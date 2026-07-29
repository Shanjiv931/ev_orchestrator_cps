def _create_charger(client) -> str:
    station_id = client.post("/stations", json={"station_type": "public_dc_hub", "lat": 12.9, "lon": 77.6}).json()["id"]
    charger = client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})
    return charger.json()["id"]


def test_maintenance_check_updates_risk_score(client):
    charger_id = _create_charger(client)

    response = client.post(f"/stations/chargers/{charger_id}/maintenance-check", json={
        "total_sessions": 100, "aborted_sessions": 45, "error_count": 3,
    })
    assert response.status_code == 200
    assert response.json()["maintenance_risk_score"] >= 0.5


def test_maintenance_check_on_missing_charger_404s(client):
    response = client.post("/stations/chargers/00000000-0000-0000-0000-000000000000/maintenance-check", json={
        "total_sessions": 10, "aborted_sessions": 1, "error_count": 0,
    })
    assert response.status_code == 404
