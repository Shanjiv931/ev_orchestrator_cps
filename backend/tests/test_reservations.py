from datetime import datetime, timedelta, timezone


def _create_station_with_chargers(client, count: int = 2) -> str:
    station = client.post("/stations", json={"station_type": "public_dc_hub", "lat": 12.97, "lon": 79.13})
    station_id = station.json()["id"]
    for _ in range(count):
        client.post(f"/stations/{station_id}/chargers", json={"power_kw": 60.0})
    return station_id


def test_reserve_any_holds_the_lowest_port_and_sets_expiry(client, auth_headers):
    headers = auth_headers("reserver1@example.com")
    station_id = _create_station_with_chargers(client, count=2)

    reserved = client.post(f"/stations/{station_id}/reserve-any", headers=headers)
    assert reserved.status_code == 200
    body = reserved.json()
    assert body["status"] == "reserved"
    assert body["reserved_until"] is not None
    assert body["port_number"] == 1


def test_reserve_any_409s_when_none_available(client, auth_headers):
    headers = auth_headers("reserver2@example.com")
    station_id = _create_station_with_chargers(client, count=1)

    client.post(f"/stations/{station_id}/reserve-any", headers=headers)
    second = client.post(f"/stations/{station_id}/reserve-any", headers=auth_headers("reserver3@example.com"))
    assert second.status_code == 409


def test_reserved_charger_is_not_offered_to_start_at_station_for_a_different_user(
    client, auth_headers, create_test_vehicle,
):
    reserver_headers = auth_headers("reserver4@example.com")
    other_email = "reserver5@example.com"
    other_headers = auth_headers(other_email)
    other_vehicle_id = str(create_test_vehicle(other_email).id)
    station_id = _create_station_with_chargers(client, count=1)

    client.post(f"/stations/{station_id}/reserve-any", headers=reserver_headers)

    blocked = client.post("/sessions/start-at-station", headers=other_headers,
                           json={"vehicle_id": other_vehicle_id, "station_id": station_id})
    assert blocked.status_code == 409


def test_reserving_user_can_claim_their_own_held_port(client, auth_headers, create_test_vehicle):
    email = "reserver6@example.com"
    headers = auth_headers(email)
    vehicle_id = str(create_test_vehicle(email).id)
    station_id = _create_station_with_chargers(client, count=1)

    reserved = client.post(f"/stations/{station_id}/reserve-any", headers=headers).json()

    started = client.post("/sessions/start-at-station", headers=headers,
                           json={"vehicle_id": vehicle_id, "station_id": station_id})
    assert started.status_code == 201
    assert started.json()["charger_id"] == reserved["id"]

    station = client.get(f"/stations/{station_id}").json()
    charger = station["chargers"][0]
    assert charger["status"] == "occupied"
    assert charger["reserved_until"] is None


def test_cancel_reservation_frees_the_port(client, auth_headers):
    headers = auth_headers("reserver7@example.com")
    station_id = _create_station_with_chargers(client, count=1)

    reserved = client.post(f"/stations/{station_id}/reserve-any", headers=headers).json()
    cancelled = client.post(f"/stations/chargers/{reserved['id']}/cancel-reservation", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "available"


def test_expired_reservation_is_lazily_released_on_next_read(client, auth_headers, db_session):
    from app.models import Charger

    headers = auth_headers("reserver8@example.com")
    station_id = _create_station_with_chargers(client, count=1)
    reserved = client.post(f"/stations/{station_id}/reserve-any", headers=headers).json()

    charger = db_session.get(Charger, reserved["id"])
    charger.reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    station = client.get(f"/stations/{station_id}").json()
    assert station["chargers"][0]["status"] == "available"
    assert station["chargers"][0]["reserved_until"] is None
