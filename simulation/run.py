"""Simulation layer entrypoint.

Phase 1 scope: boot cleanly and prove MQTT connectivity. The real SUMO/TraCI
city + corridor scenarios, station/swap/grid/solar sims are built in Phase 2.
"""
import logging
import os
import time

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s simulation %(message)s")
log = logging.getLogger("simulation")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)

    log.info("connected to MQTT broker at %s:%s, awaiting Phase 2 scenarios", MQTT_HOST, MQTT_PORT)
    client.loop_forever()


if __name__ == "__main__":
    main()
