from typing import cast

from redis.asyncio import Redis

from packages.config.settings import Settings

STREAM_HIGH = "meridian:reviews:high"
STREAM_MEDIUM = "meridian:reviews:medium"
STREAM_LOW = "meridian:reviews:low"
STREAM_DEADLETTER = "meridian:reviews:deadletter"
CONSUMER_GROUP = "meridian-workers"


def create_redis_client(settings: Settings) -> Redis:
    """Create an async Redis client from settings."""
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    return cast("Redis", client)
