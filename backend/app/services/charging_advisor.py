"""Rules-based "is now a good time to charge" advisory (Section 5-adjacent
beyond-scope module) combining three independent signals: real weather,
live feeder load (from twin-engine, the same data AdminPage.tsx's Feeder
load cards show), and a time-of-day tariff heuristic.

Deliberately rules-based rather than a trained model - the whole point of
an advisory a driver has to trust and act on is that its reasoning is
inspectable and stateable in one sentence per factor, not a black box.
Each factor can only ever downgrade the overall level (good -> fair ->
poor), never upgrade past what another factor already capped it at, so a
single serious issue (grid overload, extreme heat) can't be diluted by two
mild positives.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.services.weather_service import WeatherReading, get_current_weather

log = logging.getLogger("charging-advisor")

IST = ZoneInfo("Asia/Kolkata")
PEAK_HOURS = range(18, 22)  # 6pm-10pm IST - typical evening residential+commercial peak
_LEVEL_ORDER = {"good": 2, "fair": 1, "poor": 0}


@dataclass
class Advisory:
    level: str  # good | fair | poor
    reasons: List[str]
    temperature_c: float
    is_peak_hours: bool
    feeders_overloaded: int
    feeders_total: int


def _downgrade(current: str, new: str) -> str:
    return new if _LEVEL_ORDER[new] < _LEVEL_ORDER[current] else current


async def _fetch_feeder_states() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.twin_engine_http_url}/state/feeder")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("could not fetch feeder state for advisory (%s)", exc)
        return {}


def _weather_factor(weather: WeatherReading, level: str, reasons: List[str]) -> str:
    if weather.is_extreme_heat:
        reasons.append(
            f"Extreme heat ({weather.temperature_c:.0f}C) increases battery thermal stress and reduces "
            "charging efficiency - if it can wait for cooler hours, it's a better time later."
        )
        return _downgrade(level, "poor")
    if weather.is_rain:
        reasons.append(f"Rain ({weather.precipitation_mm:.1f}mm) - charging itself is unaffected, but allow extra travel time.")
        return _downgrade(level, "fair")
    if weather.is_fog:
        reasons.append("Low visibility may slow your trip to the station - plan extra time.")
        return _downgrade(level, "fair")
    reasons.append(f"Comfortable conditions ({weather.temperature_c:.0f}C, clear).")
    return level


def _grid_factor(feeders: dict, level: str, reasons: List[str]) -> tuple[str, int, int]:
    total = len(feeders)
    overloaded = sum(1 for f in feeders.values() if f.get("is_overloaded"))
    if total == 0:
        return level, 0, 0
    if overloaded > 0:
        reasons.append(
            f"{overloaded} of {total} Vellore feeders are near capacity right now - charging adds "
            "strain to an already-stressed part of the grid."
        )
        return _downgrade(level, "poor"), overloaded, total
    avg_loading = sum(f.get("loading_percent", 0.0) for f in feeders.values()) / total
    if avg_loading > 60.0:
        reasons.append(f"Grid load is moderate-to-high right now (avg {avg_loading:.0f}% of feeder capacity).")
        return _downgrade(level, "fair"), overloaded, total
    reasons.append("Grid load across Vellore's feeders is comfortably low right now.")
    return level, overloaded, total


def _tariff_factor(now_ist: datetime, level: str, reasons: List[str]) -> tuple[str, bool]:
    is_peak = now_ist.hour in PEAK_HOURS
    if is_peak:
        reasons.append(
            f"It's {now_ist.strftime('%-I %p')} - peak evening demand hours. Charging before 6pm or "
            "after 10pm is typically cheaper and eases load on the grid."
        )
        return _downgrade(level, "fair"), is_peak
    reasons.append("Off-peak hours - favorable for both cost and grid load.")
    return level, is_peak


async def get_charging_advisory() -> Advisory:
    weather = await get_current_weather()
    feeders = await _fetch_feeder_states()
    now_ist = datetime.now(IST)

    level = "good"
    reasons: List[str] = []
    level = _weather_factor(weather, level, reasons)
    level, overloaded, total = _grid_factor(feeders, level, reasons)
    level, is_peak = _tariff_factor(now_ist, level, reasons)

    return Advisory(
        level=level, reasons=reasons, temperature_c=weather.temperature_c,
        is_peak_hours=is_peak, feeders_overloaded=overloaded, feeders_total=total,
    )
