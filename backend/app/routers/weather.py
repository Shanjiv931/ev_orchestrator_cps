"""Real weather for Vellore (services/weather_service.py, Open-Meteo) and
the rules-based charging-time advisory built on top of it
(services/charging_advisor.py).
"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter

from app.services.charging_advisor import get_charging_advisory
from app.services.weather_service import get_current_weather

router = APIRouter(prefix="/weather", tags=["weather"])


class WeatherResponse(BaseModel):
    temperature_c: float
    apparent_temperature_c: float
    humidity_pct: float
    precipitation_mm: float
    wind_speed_kmh: float
    is_rain: bool
    is_fog: bool
    is_extreme_heat: bool
    stale: bool


class AdvisoryResponse(BaseModel):
    level: str
    reasons: list[str]
    temperature_c: float
    is_peak_hours: bool
    feeders_overloaded: int
    feeders_total: int


@router.get("/current", response_model=WeatherResponse)
async def current_weather() -> WeatherResponse:
    reading = await get_current_weather()
    return WeatherResponse(
        temperature_c=reading.temperature_c,
        apparent_temperature_c=reading.apparent_temperature_c,
        humidity_pct=reading.humidity_pct,
        precipitation_mm=reading.precipitation_mm,
        wind_speed_kmh=reading.wind_speed_kmh,
        is_rain=reading.is_rain,
        is_fog=reading.is_fog,
        is_extreme_heat=reading.is_extreme_heat,
        stale=reading.stale,
    )


@router.get("/advisory", response_model=AdvisoryResponse)
async def charging_advisory() -> AdvisoryResponse:
    advisory = await get_charging_advisory()
    return AdvisoryResponse(
        level=advisory.level, reasons=advisory.reasons, temperature_c=advisory.temperature_c,
        is_peak_hours=advisory.is_peak_hours, feeders_overloaded=advisory.feeders_overloaded,
        feeders_total=advisory.feeders_total,
    )
