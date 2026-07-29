def _v2g_vehicle(**overrides) -> dict:
    defaults = dict(
        id="v1", is_pluggable=True, v2g_capable=True, opted_in=True, is_parked=True,
        soc_pct=85.0, battery_capacity_kwh=60.0, max_discharge_kw=7.0,
    )
    defaults.update(overrides)
    return defaults


def test_v2g_dispatch_endpoint(client):
    response = client.post("/v2g/dispatch", json={
        "vehicles": [_v2g_vehicle(id="a"), _v2g_vehicle(id="b")],
        "feeder_deficit_kw": 10.0,
        "duration_hours": 1.0,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["total_dispatched_kw"] > 0


def test_blackout_plan_endpoint(client):
    response = client.post("/blackout/plan", json={
        "critical_load": {"id": "clinic-1", "name": "Test Clinic", "lat": 12.935, "lon": 77.615, "required_kw": 5.0},
        "vehicles": [_v2g_vehicle(id="a")],
        "vehicle_positions": {"a": [12.935, 77.615]},
        "max_radius_km": 3.0,
        "duration_hours": 2.0,
    })
    assert response.status_code == 200
    assert response.json()["coverage_ratio"] > 0


def test_solar_sync_recommend_endpoint(client):
    response = client.post("/solar-sync/recommend", json={
        "current_hour": 10, "session_duration_hours": 2, "station_has_solar": True,
        "peak_generation_kw": 7.0, "load_kw": 7.0,
    })
    assert response.status_code == 200
    assert 9 <= response.json()["recommended_start_hour"] <= 15


def test_recommendations_endpoint_ranks_compatible_candidates(client):
    response = client.post("/recommendations", json={
        "vehicle": {"connector_type": "CCS2", "is_pluggable": True},
        "candidates": [{
            "id": "c1", "kind": "charge", "connector_type": "CCS2", "lat": 12.936, "lon": 77.616,
            "predicted_wait_minutes": 5, "cost_rupees": 20, "congestion_risk": 0.1,
            "last_verified_at": "2026-01-01T12:00:00+00:00", "reported_status": "available",
        }],
        "user_lat": 12.935, "user_lon": 77.615,
    })
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["candidate_id"] == "c1"


def test_emergency_queue_insert_endpoint_jumps_when_under_cap(client):
    response = client.post("/emergency-queue/insert", json={
        "queue_key": "charger-test-1", "request_id": "r1", "vehicle_id": "ambulance-1", "is_emergency": True,
    })
    assert response.status_code == 200
    assert response.json()["jumped_queue"] is True


def test_stress_test_sweep_endpoint(client):
    response = client.post("/stress-test/sweep", json={
        "feeder_id": "feeder-x", "feeder_capacity_kw": 100.0, "baseline_vehicle_count": 20,
        "avg_charger_power_kw": 7.0, "simultaneous_charge_fraction": 0.5,
        "density_multipliers": [1.0, 3.0, 5.0], "station_capacity_kw": 100.0,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["breaking_point_multiplier"] is not None
    assert body["recommended_additional_stations"] >= 0
