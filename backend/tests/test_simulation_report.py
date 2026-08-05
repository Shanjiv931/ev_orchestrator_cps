def test_simulation_report_returns_the_expected_shape(client):
    """Not a full integration test of every number (that needs a live
    twin-engine/MQTT stack) - confirms the endpoint aggregates DB state
    into the shape a paper's results section would pull numbers from, and
    degrades gracefully (grid section present but empty) when twin-engine
    isn't reachable, matching every other twin-dependent endpoint's
    behavior in this test environment."""
    response = client.get("/simulation/report")
    assert response.status_code == 200
    body = response.json()

    assert "generated_at" in body
    assert set(body["chargers"]) == {"total", "by_status", "utilization_pct"}
    assert set(body["queueing"]) == {
        "stations_with_active_queue", "total_queued_vehicles", "avg_estimated_wait_minutes",
    }
    assert set(body["energy_last_24h"]) == {
        "sessions_completed", "total_energy_kwh", "avg_energy_kwh_per_session",
    }
    assert set(body["fault_detection"]) == {
        "window_seconds", "critical_fault_count", "warning_fault_count", "chargers_with_active_faults",
    }
    assert set(body["grid"]) == {"feeders_reporting", "feeders_overloaded", "avg_transformer_loading_pct"}


def test_simulation_report_reflects_charger_status_counts(client):
    """Asserts on total count and that by_status sums back to it, not on a
    specific status - the session-scoped TestClient's lifespan starts a
    real fault-consumer thread against the live MQTT broker (see
    app/main.py), so a newly created charger can legitimately land in
    "maintenance" instead of "available" if a live simulated fault happens
    to be nearest-matched to it during the test window."""
    before_total = client.get("/simulation/report").json()["chargers"]["total"]

    station = client.post("/stations", json={"station_type": "public_dc_hub", "lat": 12.97, "lon": 79.13})
    station_id = station.json()["id"]
    client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})
    client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})

    after = client.get("/simulation/report").json()["chargers"]
    assert after["total"] == before_total + 2
    assert sum(after["by_status"].values()) == after["total"]
