"""Solar-synced smart charging (Section 5.3).

Biases a charging schedule toward daylight hours at solar-equipped
stations, using the same diurnal generation curve `simulation/solar_sim.py`
publishes, combined with the Time-of-Day tariff structure - so a solar
station's recommended start time skews toward midday even when the
cheapest ToD rate alone might suggest late night.
"""
from __future__ import annotations

import math

SUNRISE_HOUR = 6.0
SUNSET_HOUR = 18.0

# A representative Indian residential/commercial ToD tariff (rupees/kWh):
# off-peak overnight is cheapest, evening peak is most expensive.
DEFAULT_TOD_TARIFF_BY_HOUR = {h: 8.0 for h in range(24)}
DEFAULT_TOD_TARIFF_BY_HOUR.update({h: 5.0 for h in range(0, 6)})       # night off-peak
DEFAULT_TOD_TARIFF_BY_HOUR.update({h: 9.5 for h in range(18, 22)})     # evening peak


def solar_generation_kw_at(hour_of_day: float, peak_generation_kw: float) -> float:
    if hour_of_day <= SUNRISE_HOUR or hour_of_day >= SUNSET_HOUR:
        return 0.0
    phase = (hour_of_day - SUNRISE_HOUR) / (SUNSET_HOUR - SUNRISE_HOUR)
    return peak_generation_kw * math.sin(math.pi * phase)


def _effective_cost_per_kwh(hour: int, tariff_by_hour: dict[int, float], station_has_solar: bool,
                             peak_generation_kw: float, load_kw: float) -> float:
    tariff = tariff_by_hour.get(hour, 8.0)
    if not station_has_solar or load_kw <= 0:
        return tariff
    solar_kw = solar_generation_kw_at(hour, peak_generation_kw)
    solar_offset_fraction = min(1.0, solar_kw / load_kw)
    return tariff * (1.0 - solar_offset_fraction)


def recommend_charging_window(current_hour: int, session_duration_hours: int, station_has_solar: bool,
                               peak_generation_kw: float, load_kw: float,
                               tariff_by_hour: dict[int, float] | None = None,
                               lookahead_hours: int = 24) -> dict:
    """Picks the start hour (within the lookahead window) that minimizes
    total effective cost - tariff paid minus the value of solar generation
    offsetting grid draw during the session."""
    tariff_by_hour = tariff_by_hour or DEFAULT_TOD_TARIFF_BY_HOUR
    best_start = current_hour
    best_cost = float("inf")

    for offset in range(lookahead_hours):
        start_hour = (current_hour + offset) % 24
        total_cost = sum(
            _effective_cost_per_kwh((start_hour + h) % 24, tariff_by_hour, station_has_solar, peak_generation_kw, load_kw)
            for h in range(session_duration_hours)
        )
        if total_cost < best_cost:
            best_cost = total_cost
            best_start = start_hour

    return {"recommended_start_hour": best_start, "estimated_cost_per_kwh_total": round(best_cost, 3)}
