"""Digital twin engine entrypoint.

Phase 1 scope: boot cleanly and prove MQTT connectivity so the container is a
real, verifiable member of the stack. State ingestion, Redis caching, and the
WebSocket read API are built in Phase 3 once the simulation layer (Phase 2) is
producing real telemetry to subscribe to.
"""
import logging
import os
import time

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s twin-engine %(message)s")
log = logging.getLogger("twin-engine")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))


def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
    log.info("connected to MQTT broker at %s:%s (reason=%s)", MQTT_HOST, MQTT_PORT, reason_code)
    client.subscribe("ev/telemetry/#")
    client.subscribe("charger/status/#")
    client.subscribe("swap/status/#")
    client.subscribe("feeder/load/#")


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("MQTT broker not ready (%s), retrying in 2s", exc)
            time.sleep(2)

    client.loop_forever()


if __name__ == "__main__":
    main()
