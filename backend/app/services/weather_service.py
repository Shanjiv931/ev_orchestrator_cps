"""Real weather for Vellore via Open-Meteo (https://open-meteo.com) - free,
no API key, no signup, matches this project's own "zero-cost" framing
(README.md). Chosen over a keyed provider (OpenWeatherMap etc.) specifically
because a paper's readers/reviewers should be able to reproduce results
without provisioning a credential.

Short-TTL in-memory cache: Open-Meteo's fair-use policy is generous but not
unlimited, and nothing about charging-advisory freshness needs sub-minute
weather data. On a fetch failure the last good reading is served (however
stale) rather than raising, since a transient weather-API outage should
degrade the advisory, not the whole app.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.scenario_engine import DEFAULT_TARGET_LAT, DEFAULT_TARGET_LON

log = logging.getLogger("weather-service")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_SECONDS = 20 * 60

# WMO weather codes (the standard Open-Meteo reports in) collapsed into the
# handful of conditions the rest of the app actually reasons about.
_RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
_FOG_CODES = {45, 48}


@dataclass
class WeatherReading:
    temperature_c: float
    apparent_temperature_c: float
    humidity_pct: float
    precipitation_mm: float
    wind_speed_kmh: float
    weather_code: int
    is_rain: bool
    is_fog: bool
    is_extreme_heat: bool  # >= 40C, a real pre-monsoon Vellore summer condition
    fetched_at: float
    stale: bool = False


_cache: Optional[WeatherReading] = None
_cache_fetched_at: float = 0.0


async def get_current_weather(lat: float = DEFAULT_TARGET_LAT, lon: float = DEFAULT_TARGET_LON) -> WeatherReading:
    global _cache, _cache_fetched_at
    now = time.time()
    if _cache is not None and (now - _cache_fetched_at) < CACHE_TTL_SECONDS:
        return _cache

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(OPEN_METEO_URL, params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "timezone": "Asia/Kolkata",
            })
            response.raise_for_status()
            current = response.json()["current"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Open-Meteo fetch failed (%s)", exc)
        if _cache is not None:
            return WeatherReading(**{**_cache.__dict__, "stale": True})
        # No prior reading to fall back to - a clearly-marked neutral
        # reading rather than raising, so a weather-API outage degrades
        # the advisory rather than the page that shows it.
        return WeatherReading(
            temperature_c=28.0, apparent_temperature_c=28.0, humidity_pct=60.0,
            precipitation_mm=0.0, wind_speed_kmh=0.0, weather_code=0,
            is_rain=False, is_fog=False, is_extreme_heat=False, fetched_at=now, stale=True,
        )

    weather_code = int(current["weather_code"])
    temperature_c = float(current["temperature_2m"])
    reading = WeatherReading(
        temperature_c=temperature_c,
        apparent_temperature_c=float(current["apparent_temperature"]),
        humidity_pct=float(current["relative_humidity_2m"]),
        precipitation_mm=float(current["precipitation"]),
        wind_speed_kmh=float(current["wind_speed_10m"]),
        weather_code=weather_code,
        is_rain=weather_code in _RAIN_CODES,
        is_fog=weather_code in _FOG_CODES,
        is_extreme_heat=temperature_c >= 40.0,
        fetched_at=now,
    )
    _cache, _cache_fetched_at = reading, now
    return reading
