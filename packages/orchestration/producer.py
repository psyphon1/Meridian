"""Redis Streams producer — XADD job messages to priority streams (Task 20)."""

from redis.asyncio import Redis

from packages.models.schemas import JobMessage


async def enqueue_job(redis: Redis, priority: str, job: JobMessage) -> str:
    """XADD a job message to the appropriate priority stream.

    Called by the outbox publisher (apps/worker/outbox_publisher.py), NOT
    by the webhook handler directly. Decouples Redis from the 10-second
    webhook critical path (ADR-006).

    Returns the Redis stream ID.
    """
    stream = f"meridian:reviews:{priority}"
    msg_id = await redis.xadd(stream, {"data": job.model_dump_json()})
    return str(msg_id)