"""Daily demand-model retraining (point 13) - blends real charging behavior
(app/models/entities.py's ChargingBehaviorLog, populated as sessions
complete - see app/routers/sessions.py) behind the synthetic baseline
(ml/demand_forecast.generate_synthetic_history) so the model always has
enough data to fit, while what actually happened becomes an increasingly
large share of it as real history accumulates. Callable as a script (a
production cron target, matching app/services/retention_job.py's own
`if __name__ == "__main__"` pattern) or via POST /admin/retrain-demand-model,
so "every day" here means "whatever schedule the operator's cron runs it on"
rather than a scheduler this repo owns.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChargingBehaviorLog, DemandModelTrainingRun
from ml.demand_forecast import generate_synthetic_history, train_and_evaluate

# Retrained lazily on first request, then reused until force_retrain() is
# called - matches the "trained once per process" tradeoff the original
# advanced_features.py cache already made (XGBoost fit takes a couple of
# seconds), just now sourced from real+synthetic history instead of purely
# synthetic.
_cached_result: dict = {}


def _aggregate_real_history(logs: list[ChargingBehaviorLog]) -> pd.DataFrame:
    """One row per completed session isn't the shape train_and_evaluate
    expects (session *counts* per zone/hour/day, not per-session rows) -
    this aggregates real logs into that shape, using each log's actual
    calendar date to assign day_index, so distinct real days really are
    distinct in the training data rather than collapsed together."""
    columns = ["day_index", "zone", "hour", "day_of_week", "weather", "sessions"]
    if not logs:
        return pd.DataFrame(columns=columns)

    dates = sorted({log.logged_at.date() for log in logs})
    date_to_index = {d: i for i, d in enumerate(dates)}
    rows = [
        {
            "day_index": date_to_index[log.logged_at.date()],
            "zone": log.zone, "hour": log.hour, "day_of_week": log.day_of_week, "weather": 0,
        }
        for log in logs
    ]
    frame = pd.DataFrame(rows)
    return frame.groupby(["day_index", "zone", "hour", "day_of_week", "weather"]).size().reset_index(name="sessions")


def build_training_history(db: Session) -> tuple[pd.DataFrame, int, int]:
    """Synthetic history first (as the oldest days), real history appended
    after (as the most recent days) - so the model reflects real behavior
    once there's enough of it, without ever training on zero rows before
    any real session has ever completed."""
    synthetic = generate_synthetic_history()
    real_logs = list(db.scalars(select(ChargingBehaviorLog)).all())
    real = _aggregate_real_history(real_logs)

    if not real.empty:
        real = real.copy()
        real["day_index"] = real["day_index"] + synthetic["day_index"].max() + 1
        combined = pd.concat([synthetic, real], ignore_index=True)
    else:
        combined = synthetic

    return combined, len(real_logs), len(synthetic)


def retrain(db: Session) -> dict:
    history, real_rows, synthetic_rows = build_training_history(db)
    result = train_and_evaluate(history=history)
    result["real_data_rows"] = real_rows
    result["synthetic_rows"] = synthetic_rows

    db.add(DemandModelTrainingRun(
        real_data_rows=real_rows, synthetic_rows=synthetic_rows,
        mae=result["mae"], rmse=result["rmse"],
    ))
    db.commit()

    return result


def get_or_train_model(db: Session) -> dict:
    if "model" not in _cached_result:
        _cached_result.update(retrain(db))
    return _cached_result


def force_retrain(db: Session) -> dict:
    result = retrain(db)
    _cached_result.clear()
    _cached_result.update(result)
    return _cached_result


if __name__ == "__main__":
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        outcome = force_retrain(session)
        print(
            f"Demand model retrained: MAE={outcome['mae']:.3f} RMSE={outcome['rmse']:.3f} "
            f"({outcome['real_data_rows']} real behavior-log rows, {outcome['synthetic_rows']} synthetic backfill rows)"
        )
    finally:
        session.close()
