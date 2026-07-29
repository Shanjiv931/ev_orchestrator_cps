from datetime import datetime, timedelta, timezone

from ml.emergency_queue import PriorityJumpTracker, QueuedRequest, insert_with_priority

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _request(id_: str, vehicle_id: str, is_emergency: bool = False, when: datetime = NOW) -> QueuedRequest:
    return QueuedRequest(id=id_, vehicle_id=vehicle_id, is_emergency=is_emergency, requested_at=when)


def test_emergency_request_jumps_ahead_of_normal_queue():
    queue = [_request("r1", "v1"), _request("r2", "v2")]
    tracker = PriorityJumpTracker()
    emergency = _request("r3", "ambulance-1", is_emergency=True)

    updated = insert_with_priority(queue, emergency, tracker, NOW)
    assert updated[0].id == "r3"


def test_normal_request_goes_to_the_back():
    queue = [_request("r1", "v1")]
    tracker = PriorityJumpTracker()
    normal = _request("r2", "v2")

    updated = insert_with_priority(queue, normal, tracker, NOW)
    assert updated[-1].id == "r2"


def test_priority_jumps_are_capped_within_the_rolling_window():
    """Starvation protection: once the cap is hit, further emergency
    requests in the same window queue normally instead of continuing to
    jump ahead of everyone."""
    queue: list[QueuedRequest] = []
    tracker = PriorityJumpTracker()

    for i in range(3):
        queue = insert_with_priority(queue, _request(f"e{i}", f"amb{i}", is_emergency=True), tracker, NOW)
    assert [r.id for r in queue] == ["e2", "e1", "e0"]  # each jumped ahead of the previous

    fourth = _request("e3", "amb3", is_emergency=True)
    queue = insert_with_priority(queue, fourth, tracker, NOW)
    assert queue[-1].id == "e3"  # cap hit: goes to the back like a normal request


def test_jump_cap_resets_after_the_rolling_window_elapses():
    tracker = PriorityJumpTracker()
    queue: list[QueuedRequest] = []
    for i in range(3):
        queue = insert_with_priority(queue, _request(f"e{i}", f"amb{i}", is_emergency=True), tracker, NOW)

    later = NOW + timedelta(hours=2)
    fourth = _request("e3", "amb3", is_emergency=True)
    queue = insert_with_priority(queue, fourth, tracker, later)
    assert queue[0].id == "e3"  # window elapsed: jump allowed again


def test_normal_users_are_not_starved_once_jump_cap_is_reached():
    tracker = PriorityJumpTracker()
    queue: list[QueuedRequest] = []
    for i in range(3):
        queue = insert_with_priority(queue, _request(f"e{i}", f"amb{i}", is_emergency=True), tracker, NOW)

    normal = _request("normal-1", "v1")
    queue = insert_with_priority(queue, normal, tracker, NOW)
    over_cap_emergency = _request("e3", "amb3", is_emergency=True)
    queue = insert_with_priority(queue, over_cap_emergency, tracker, NOW)

    # the over-cap "emergency" request queues behind the normal request it arrived after
    assert queue.index(over_cap_emergency) > queue.index(normal)
