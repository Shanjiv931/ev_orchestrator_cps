"""Emergency/priority queueing (Section 5.5).

Lets a tagged emergency vehicle (ambulance, disaster-response fleet) jump
a charging/swap queue - but bounded: a station that let priority jumps
happen unconditionally would let a single emergency vehicle (or a bad
actor mislabeling itself) starve every normal user indefinitely. The cap
here is deliberately on jump *frequency* within a rolling window, not on
duration held, since queue position (not session length) is what "jumping
the queue" actually controls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

MAX_PRIORITY_JUMPS_PER_WINDOW = 3
PRIORITY_JUMP_WINDOW = timedelta(hours=1)


@dataclass
class QueuedRequest:
    id: str
    vehicle_id: str
    is_emergency: bool
    requested_at: datetime


@dataclass
class PriorityJumpTracker:
    """Tracks recent jumps for a single station/swap-point queue."""
    jump_timestamps: list[datetime] = field(default_factory=list)

    def _prune(self, now: datetime) -> None:
        cutoff = now - PRIORITY_JUMP_WINDOW
        self.jump_timestamps = [t for t in self.jump_timestamps if t >= cutoff]

    def can_jump(self, now: datetime) -> bool:
        self._prune(now)
        return len(self.jump_timestamps) < MAX_PRIORITY_JUMPS_PER_WINDOW

    def record_jump(self, now: datetime) -> None:
        self._prune(now)
        self.jump_timestamps.append(now)


def insert_with_priority(queue: list[QueuedRequest], new_request: QueuedRequest,
                          tracker: PriorityJumpTracker, now: datetime) -> list[QueuedRequest]:
    """Emergency requests go to the front of the queue, unless the jump cap
    for this queue has already been hit in the current rolling window - in
    which case they queue normally, like everyone else."""
    if new_request.is_emergency and tracker.can_jump(now):
        tracker.record_jump(now)
        return [new_request] + queue
    return queue + [new_request]
