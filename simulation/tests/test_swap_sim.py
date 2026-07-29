import random
import sys
from pathlib import Path

import simpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from registry import SwapKioskSpec
from swap_sim import MAX_TURNAROUND_SECONDS, SwapKiosk


def test_single_swap_turnaround_is_sub_two_minutes():
    spec = SwapKioskSpec("k1", "feeder-x", total_batteries=5, cabinet_power_kw=15.0)
    env = simpy.Environment()
    events = []
    random.seed(1)
    kiosk = SwapKiosk(env=env, spec=spec, publish=events.append)

    start = env.now
    proc = env.process(kiosk.swap_session())

    def _record_completion():
        yield proc
        events.append({"__completed_at": env.now})

    env.process(_record_completion())
    env.run(until=10)

    completion = next(e for e in events if "__completed_at" in e)
    elapsed_minutes = completion["__completed_at"] - start
    assert elapsed_minutes * 60.0 <= MAX_TURNAROUND_SECONDS


def test_arrival_queues_when_pool_is_empty_and_unblocks_after_recharge():
    """With zero spare batteries, a swap request must wait for a battery to
    come back from the cabinet - the real constraint at a busy kiosk."""
    spec = SwapKioskSpec("k2", "feeder-x", total_batteries=1, cabinet_power_kw=15.0)
    env = simpy.Environment()
    events = []
    random.seed(2)
    kiosk = SwapKiosk(env=env, spec=spec, publish=events.append)

    env.process(kiosk.swap_session())  # takes the only battery
    env.run(until=1)
    assert int(kiosk.available.level) == 0

    second_done = []
    def second_request():
        yield env.process(kiosk.swap_session())
        second_done.append(env.now)

    env.process(second_request())
    env.run(until=1.5)
    assert not second_done, "second swap must not complete before a battery is recharged"

    env.run(until=500)
    assert second_done, "second swap must eventually complete once a battery recharges"


def test_batteries_available_and_charging_never_exceed_total():
    spec = SwapKioskSpec("k3", "feeder-x", total_batteries=3, cabinet_power_kw=15.0)
    env = simpy.Environment()
    events = []
    random.seed(3)
    kiosk = SwapKiosk(env=env, spec=spec, publish=events.append)
    env.process(kiosk.arrivals())
    env.run(until=600)

    for e in events:
        if "batteries_available" not in e:
            continue
        assert e["batteries_available"] + e["batteries_charging"] <= spec.total_batteries
        assert 0 <= e["batteries_available"] <= spec.total_batteries


def test_power_draw_scales_with_batteries_charging():
    spec = SwapKioskSpec("k4", "feeder-x", total_batteries=4, cabinet_power_kw=20.0)
    env = simpy.Environment()
    events = []
    kiosk = SwapKiosk(env=env, spec=spec, publish=events.append)

    kiosk.charging_count = 2
    kiosk._publish_status()

    latest = events[-1]
    assert latest["power_kw"] == 10.0  # 2/4 of cabinet_power_kw
