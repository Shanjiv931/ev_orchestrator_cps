"""Thin Redis client for ephemeral state that should never be treated as
"saved" data - currently just pending (not-yet-verified) registrations.
redis_url has been a config value since early in this project but the main
backend never actually connected to Redis (only twin-engine does) - this is
the first real use of it here."""
import redis

from app.config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
