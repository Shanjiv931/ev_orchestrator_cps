"""Mass-gathering stress-test mode (Section 5.6): live scenario side.

A one-command scenario that spikes simulated EV density at a target
station for a burst window, reusing station_sim.py's own Station/queueing
machinery (just with a much higher arrival rate) rather than a separate
simulator - a festival rush or pilgrimage-travel event is the same queueing
problem as normal operation, just at far higher density. The analysis of
where this causes the grid/recommendation systems to break down lives in
`backend/ml/event_stress_test.py`, which this module's MQTT output feeds.
"""
from __future__ import annotations

import argparse
import logging
import os
import time

import simpy
import simpy.rt

from registry import STATIONS_BY_ID
from station_sim import STATION_PROFILES, Station

logging.basicConfig(level=logging.INFO, format="%(asctime)s event-stress-sim %(message)s")
log = logging.getLogger("event-stress-sim")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))


def run_burst(station_id: str, density_multiplier: float, burst_minutes: float, publish,
              realtime_factor: float | None = 1.0, env: simpy.Environment | None = None) -> None:
    """realtime_factor is real seconds per simulated minute (SimPy's
    RealtimeEnvironment convention) - used for the live demo. Tests instead
    pass a plain `env=simpy.Environment()` to run the same logic instantly,
    the same pattern station_sim.py's own tests use."""
    if station_id not in STATIONS_BY_ID:
        raise ValueError(f"unknown station_id: {station_id}")
    spec = STATIONS_BY_ID[station_id]

    mean_interarrival, mean_session, offline_prob, mean_offline = STATION_PROFILES[spec.station_type]
    boosted_profile = (mean_interarrival / density_multiplier, mean_session, offline_prob, mean_offline)
    STATION_PROFILES[spec.station_type] = boosted_profile  # module-level override for the burst's duration
    log.warning("STRESS TEST: %s density x%.1f for %.0f minutes (mean interarrival %.1f -> %.1f min)",
                station_id, density_multiplier, burst_minutes, mean_interarrival, boosted_profile[0])

    try:
        if env is None:
            env = simpy.rt.RealtimeEnvironment(factor=realtime_factor, strict=False)
        station = Station(env=env, spec=spec, publish=publish)
        env.process(station.arrivals())
        env.run(until=burst_minutes)
    finally:
        STATION_PROFILES[spec.station_type] = (mean_interarrival, mean_session, offline_prob, mean_offline)
        log.warning("STRESS TEST complete for %s, profile restored to baseline", station_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--density-multiplier", type=float, default=5.0)
    parser.add_argument("--burst-minutes", type=float, default=30.0)
    parser.add_argument("--realtime-factor", type=float, default=1.0)
    args = parser.parse_args()

    import json

    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)
    client.loop_start()

    def publish(payload: dict) -> None:
        client.publish(f"charger/status/{payload['charger_id']}", json.dumps(payload), qos=0)

    run_burst(args.station_id, args.density_multiplier, args.burst_minutes, publish, args.realtime_factor)
    client.loop_stop()


if __name__ == "__main__":
    main()
