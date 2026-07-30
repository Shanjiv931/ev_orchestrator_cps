from app.models import Charger, Station, SwapSlot
from app.seed_stations import STATION_SEEDS, seed_stations_if_empty


def test_seed_stations_if_empty_populates_multiple_cities(db_session):
    seed_stations_if_empty(db_session)
    assert db_session.query(Station).count() == len(STATION_SEEDS)


def test_seed_stations_creates_chargers_and_swap_slots(db_session):
    seed_stations_if_empty(db_session)
    assert db_session.query(Charger).count() > 20
    assert db_session.query(SwapSlot).count() > 0


def test_seed_stations_is_idempotent(db_session):
    seed_stations_if_empty(db_session)
    seed_stations_if_empty(db_session)
    assert db_session.query(Station).count() == len(STATION_SEEDS)


def test_seeded_stations_span_a_wide_geographic_area(client, db_session):
    seed_stations_if_empty(db_session)
    response = client.get("/stations")
    assert response.status_code == 200
    lats = {s["lat"] for s in response.json()}
    assert len(lats) > 10  # many distinct cities/areas, not one city repeated
