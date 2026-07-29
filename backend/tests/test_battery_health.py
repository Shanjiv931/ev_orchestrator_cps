def _create_vehicle(client, headers) -> str:
    created = client.post("/vehicles", headers=headers, json={
        "vehicle_class": "4W", "connector_type": "CCS2", "battery_chemistry": "NMC", "is_pluggable": True,
    })
    return created.json()["id"]


def test_soh_is_reported_separately_from_soc():
    """Section 4.5.4: SoH must never be merged with SoC anywhere in the API.
    BatteryHealthRead only has soh_pct - there is no soc field to conflate it
    with; this test pins that shape."""
    from app.schemas import BatteryHealthRead

    fields = BatteryHealthRead.model_fields.keys()
    assert "soh_pct" in fields
    assert "soc_pct" not in fields
    assert "battery_pct" not in fields


def test_record_and_fetch_latest_battery_health(client, auth_headers):
    headers = auth_headers("bh1@example.com")
    vehicle_id = _create_vehicle(client, headers)

    first = client.post(f"/vehicles/{vehicle_id}/battery-health", headers=headers, json={
        "soh_pct": 92.0, "projected_months_to_80pct": 30.0, "trend_flag": "stable",
    })
    assert first.status_code == 201

    second = client.post(f"/vehicles/{vehicle_id}/battery-health", headers=headers, json={
        "soh_pct": 91.5, "projected_months_to_80pct": 28.0, "trend_flag": "accelerating",
    })
    assert second.status_code == 201

    latest = client.get(f"/vehicles/{vehicle_id}/battery-health/latest", headers=headers)
    assert latest.status_code == 200
    assert latest.json()["soh_pct"] == 91.5
    assert latest.json()["trend_flag"] == "accelerating"

    history = client.get(f"/vehicles/{vehicle_id}/battery-health", headers=headers)
    assert len(history.json()) == 2


def test_latest_battery_health_404s_with_no_records(client, auth_headers):
    headers = auth_headers("bh2@example.com")
    vehicle_id = _create_vehicle(client, headers)

    response = client.get(f"/vehicles/{vehicle_id}/battery-health/latest", headers=headers)
    assert response.status_code == 404
