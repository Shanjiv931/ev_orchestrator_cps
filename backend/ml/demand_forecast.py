"""Demand forecasting: predicted charging sessions per zone per hour.

Trained on the platform's own simulated historical sessions (Section 4.5.1).
No real session-log dataset exists yet this early in the build, so
`generate_synthetic_history` produces one with the same shape real session
logs would have - zone/hour/day-of-week/weather features driving a latent
demand curve (morning + evening commute peaks, quieter weekends, rain
suppressing demand) plus Poisson sampling noise. The held-out evaluation
slice is the most recent contiguous block of days, not a random split -
this is a genuine forecasting problem, not compatible with random shuffling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

ZONES = ["koramangala_dc_hub", "indiranagar_housing", "nh48_corridor", "holenarsipura_rural"]

_ZONE_BASE_DEMAND = {
    "koramangala_dc_hub": 14.0,
    "indiranagar_housing": 5.0,
    "nh48_corridor": 8.0,
    "holenarsipura_rural": 1.5,
}


def _latent_demand(zone: str, hour: int, day_of_week: int, weather: int) -> float:
    base = _ZONE_BASE_DEMAND[zone]
    morning_peak = 3.0 * np.exp(-((hour - 9) ** 2) / 6.0)
    evening_peak = 4.0 * np.exp(-((hour - 18) ** 2) / 8.0)
    is_weekend = day_of_week >= 5
    weekend_factor = 0.6 if is_weekend else 1.0
    rain_factor = 0.7 if weather == 1 else 1.0
    return max(0.1, (base + morning_peak + evening_peak) * weekend_factor * rain_factor)


def generate_synthetic_history(num_days: int = 60, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for day_index in range(num_days):
        day_of_week = day_index % 7
        weather = int(rng.random() < 0.2)  # ~20% rainy days
        for hour in range(24):
            for zone in ZONES:
                mean_sessions = _latent_demand(zone, hour, day_of_week, weather)
                sessions = rng.poisson(mean_sessions)
                rows.append({
                    "day_index": day_index, "zone": zone, "hour": hour,
                    "day_of_week": day_of_week, "weather": weather, "sessions": sessions,
                })
    return pd.DataFrame(rows)


def _feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    encoded = df.copy()
    encoded["zone_code"] = encoded["zone"].map({z: i for i, z in enumerate(ZONES)})
    return encoded[["zone_code", "hour", "day_of_week", "weather"]]


def train_and_evaluate(history: pd.DataFrame | None = None, held_out_days: int = 10) -> dict:
    """Trains on all but the most recent `held_out_days` days, evaluates on
    that held-out (chronologically later) slice, and returns the fitted
    model alongside MAE/RMSE - the acceptance metric Section 4.5.1 requires."""
    if history is None:
        history = generate_synthetic_history()

    split_day = history["day_index"].max() - held_out_days
    train = history[history["day_index"] <= split_day]
    held_out = history[history["day_index"] > split_day]

    model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.1, random_state=42)
    model.fit(_feature_frame(train), train["sessions"])

    predictions = model.predict(_feature_frame(held_out))
    predictions = np.clip(predictions, 0, None)
    errors = predictions - held_out["sessions"].to_numpy()
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    return {"model": model, "mae": mae, "rmse": rmse, "held_out_rows": len(held_out)}


def predict_sessions(model: XGBRegressor, zone: str, hour: int, day_of_week: int, weather: int) -> float:
    zone_code = ZONES.index(zone)
    features = pd.DataFrame([{"zone_code": zone_code, "hour": hour, "day_of_week": day_of_week, "weather": weather}])
    return max(0.0, float(model.predict(features)[0]))
