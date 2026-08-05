"""Optional deterministic seeding, shared by every sim module that uses
`random` - unset (the default) keeps the live-demo behavior of genuinely
random variation every run; set RANDOM_SEED to get a reproducible run for
methodology/evaluation purposes (a paper's results need to be re-runnable
to the same numbers, a live demo does not)."""
import logging
import os
import random

log = logging.getLogger(__name__)

RANDOM_SEED_ENV_VAR = "RANDOM_SEED"


def get_seed() -> str | None:
    """Docker Compose sets an unset ${RANDOM_SEED:-} interpolation to an
    empty string, not an absent variable, so os.environ.get() alone can't
    tell "unset" from "set to blank" - this normalizes both to None."""
    seed = os.environ.get(RANDOM_SEED_ENV_VAR)
    return seed if seed else None


def apply_random_seed(component: str) -> None:
    seed = get_seed()
    if seed is None:
        return
    random.seed(int(seed))
    log.info("%s: RANDOM_SEED=%s applied - this run is reproducible", component, seed)
