"""Diurnal rooftop-solar generation curve for every station/kiosk that has
`has_solar=True`. Used by the solar-synced smart charging module (Section
5.3) to bias charging schedules toward daylight hours.

A clear sine-like bell curve between sunrise and sunset is realistic enough
for this purpose per the build contract; it does not attempt to model
weather. Generation is sized as a modest fraction of the site's own peak
charging demand, matching a typical rooftop installation rather than a
grid-scale solar farm.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List

from registry import SWAP_KIOSKS, STATIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s solar-sim %(message)s")
log = logging.getLogger("solar-sim")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
STEP_SECONDS = float(os.environ.get("SOLAR_SIM_STEP_SECONDS", "10"))
SUNRISE_HOUR = 6.0
SUNSET_HOUR = 18.0

PublishFn = Callable[[dict], None]


@dataclass(frozen=True)
class SolarSite:
    site_id: str
    peak_generation_kw: float


def _solar_sites() -> List[SolarSite]:
    sites: List[SolarSite] = []
    for station in STATIONS:
        if station.has_solar:
            demand_kw = station.num_chargers * station.charger_power_kw
            sites.append(SolarSite(station.station_id, peak_generation_kw=round(demand_kw * 0.3, 1)))
    for kiosk in SWAP_KIOSKS:
        if kiosk.has_solar:
            sites.append(SolarSite(kiosk.kiosk_id, peak_generation_kw=round(kiosk.cabinet_power_kw * 0.3, 1)))
    return sites


def generation_kw_at(hour_of_day: float, peak_generation_kw: float) -> float:
    if hour_of_day <= SUNRISE_HOUR or hour_of_day >= SUNSET_HOUR:
        return 0.0
    daylight_span = SUNSET_HOUR - SUNRISE_HOUR
    phase = (hour_of_day - SUNRISE_HOUR) / daylight_span
    return round(peak_generation_kw * math.sin(math.pi * phase), 2)


def hour_of_day_now() -> float:
    now = datetime.now(timezone.utc)
    return now.hour + now.minute / 60.0 + now.second / 3600.0


def publish_reading(publish: PublishFn, site: SolarSite) -> None:
    hour = hour_of_day_now()
    publish({
        "site_id": site.site_id,
        "generation_kw": generation_kw_at(hour, site.peak_generation_kw),
        "peak_generation_kw": site.peak_generation_kw,
        "hour_of_day": round(hour, 3),
        "reported_at": datetime.now(timezone.utc).isoformat(),
    })


def main() -> None:
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)

    def publish(payload: dict) -> None:
        client.publish(f"station/solar/{payload['site_id']}", json.dumps(payload), qos=0)

    sites = _solar_sites()
    log.info("solar-sim running %d solar sites", len(sites))
    try:
        while True:
            for site in sites:
                publish_reading(publish, site)
            time.sleep(STEP_SECONDS)
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
