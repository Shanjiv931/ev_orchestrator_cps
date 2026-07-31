from datetime import datetime, timezone

from app.models import ChargingBehaviorLog, ChargingSession, DemandModelTrainingRun, Vehicle
from app.services.demand_retrain_job import build_training_history, force_retrain
from ml.demand_forecast import ZONES, generate_synthetic_history


def _make_log(db_session, user_id, zone=ZONES[0], hour=9, day_of_week=1, energy_kwh=10.0) -> ChargingBehaviorLog:
    # ChargingBehaviorLog.session_id FKs to a real session row - a fake
    # session_id would just violate that constraint, so this test needs an
    # actual (if minimal) ChargingSession/Vehicle to hang the log off of.
    vehicle_row = Vehicle(
        user_id=user_id, vehicle_class="4W", connector_type="CCS2", battery_chemistry="NMC",
        is_pluggable=True, battery_capacity_kwh=40.0,
    )
    db_session.add(vehicle_row)
    db_session.commit()
    session = ChargingSession(user_id=user_id, vehicle_id=vehicle_row.id)
    db_session.add(session)
    db_session.commit()

    log = ChargingBehaviorLog(
        session_id=session.id, user_id=user_id, zone=zone, hour=hour,
        day_of_week=day_of_week, energy_kwh=energy_kwh, logged_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    db_session.commit()
    return log


def test_build_training_history_falls_back_to_synthetic_only_when_no_real_data(db_session):
    history, real_rows, synthetic_rows = build_training_history(db_session)
    assert real_rows == 0
    assert synthetic_rows > 0
    assert len(history) == synthetic_rows


def test_build_training_history_appends_real_rows_as_the_most_recent_days(db_session, auth_headers):
    auth_headers("retrain-user@example.com")
    from app.models import User
    user = db_session.query(User).filter(User.email == "retrain-user@example.com").first()
    _make_log(db_session, user.id, hour=9)
    _make_log(db_session, user.id, hour=10)  # distinct (zone, hour, day_of_week) group - a separate aggregated row

    history, real_rows, synthetic_rows = build_training_history(db_session)
    assert real_rows == 2
    synthetic_max_day_index = generate_synthetic_history()["day_index"].max()
    real_slice = history[history["day_index"] > synthetic_max_day_index]
    assert len(real_slice) == 2
    assert real_slice["sessions"].sum() == 2


def test_force_retrain_persists_a_training_run_row(db_session):
    before = db_session.query(DemandModelTrainingRun).count()
    result = force_retrain(db_session)
    after = db_session.query(DemandModelTrainingRun).count()

    assert after == before + 1
    assert "model" in result
    assert result["real_data_rows"] == 0
