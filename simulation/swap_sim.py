"""Battery-swap kiosk simulation.

A swap kiosk is not a generic queue - it is a battery inventory problem
(Section 4.4). The vehicle-facing operation is a near-instant handoff
(60-120 seconds); the slow part happens entirely in the background, where a
depleted battery spends tens of minutes recharging in the cabinet before it
re-enters the ready pool. `batteries_available` is modelled as a SimPy
Container so a swap blocks (queues) only when the ready pool is actually
empty - the real constraint at a busy kiosk.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List

import simpy
import simpy.rt

from registry import SWAP_KIOSKS, SwapKioskSpec

logging.basicConfig(level=logging.INFO, format="%(asctime)s swap-sim %(message)s")
log = logging.getLogger("swap-sim")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
REALTIME_FACTOR = float(os.environ.get("SWAP_SIM_REALTIME_FACTOR", "1.0"))
MEAN_INTERARRIVAL_MINUTES = float(os.environ.get("SWAP_SIM_MEAN_INTERARRIVAL_MINUTES", "4.0"))
MEAN_RECHARGE_MINUTES = float(os.environ.get("SWAP_SIM_MEAN_RECHARGE_MINUTES", "75.0"))
MIN_TURNAROUND_SECONDS = 60.0
MAX_TURNAROUND_SECONDS = 120.0

PublishFn = Callable[[dict], None]


@dataclass
class SwapKiosk:
    env: simpy.Environment
    spec: SwapKioskSpec
    publish: PublishFn
    charging_count: int = 0
    completed_swaps: int = 0
    available: simpy.Container = field(init=False)

    def __post_init__(self) -> None:
        self.available = simpy.Container(self.env, init=self.spec.total_batteries, capacity=self.spec.total_batteries)
        self._publish_status()

    def _publish_status(self) -> None:
        batteries_available = int(self.available.level)
        power_kw = 0.0
        if self.spec.total_batteries > 0:
            power_kw = (self.charging_count / self.spec.total_batteries) * self.spec.cabinet_power_kw
        self.publish({
            "kiosk_id": self.spec.kiosk_id,
            "feeder_id": self.spec.feeder_id,
            "status": "available" if batteries_available > 0 else "occupied",
            "batteries_available": batteries_available,
            "batteries_charging": self.charging_count,
            "total_batteries": self.spec.total_batteries,
            "power_kw": round(power_kw, 2),
            "reported_at": datetime.now(timezone.utc).isoformat(),
        })

    def swap_session(self) -> simpy.events.ProcessGenerator:
        yield self.available.get(1)
        turnaround_minutes = random.uniform(MIN_TURNAROUND_SECONDS, MAX_TURNAROUND_SECONDS) / 60.0
        self.charging_count += 1
        self._publish_status()

        yield self.env.timeout(turnaround_minutes)
        self.completed_swaps += 1
        self.env.process(self._recharge_battery())

    def _recharge_battery(self) -> simpy.events.ProcessGenerator:
        recharge_minutes = max(20.0, random.gauss(MEAN_RECHARGE_MINUTES, MEAN_RECHARGE_MINUTES * 0.2))
        yield self.env.timeout(recharge_minutes)
        self.charging_count -= 1
        yield self.available.put(1)
        self._publish_status()

    def arrivals(self) -> simpy.events.ProcessGenerator:
        while True:
            yield self.env.timeout(random.expovariate(1.0 / MEAN_INTERARRIVAL_MINUTES))
            self.env.process(self.swap_session())


def build_kiosks(env: simpy.Environment, publish: PublishFn, specs: List[SwapKioskSpec] = SWAP_KIOSKS) -> List[SwapKiosk]:
    kiosks = [SwapKiosk(env=env, spec=spec, publish=publish) for spec in specs]
    for kiosk in kiosks:
        env.process(kiosk.arrivals())
    return kiosks


def main() -> None:
    import paho.mqtt.client as mqtt

    from sim_seed import apply_random_seed
    apply_random_seed("swap-sim")

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
        client.publish(f"swap/status/{payload['kiosk_id']}", json.dumps(payload), qos=0)

    env = simpy.rt.RealtimeEnvironment(factor=REALTIME_FACTOR, strict=False)
    kiosks = build_kiosks(env, publish)
    log.info("swap-sim running %d kiosks (%d batteries total)",
              len(kiosks), sum(k.spec.total_batteries for k in kiosks))
    env.run()


if __name__ == "__main__":
    main()
