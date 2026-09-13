"""Worker consumer loop — processes jobs off Redis Streams (Task 26)."""

from packages.orchestration.consumer import consume_loop
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def run_consumer_loop(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
) -> None:
    """Entry point for the consumer loop in the worker process."""
    from packages.models.schemas import JobMessage

    async def on_job(job: JobMessage) -> None:
        """Process a single job — Phase 1: mark delivery processed."""
        from packages.models.audit import WebhookDelivery
        from packages.observability.logging import get_logger
        from sqlalchemy import func, select, update

        log = get_logger("worker.consumer")

        async with session_factory() as session, session.begin():
            # Fetch full payload by delivery_id
            deliv = (
                await session.execute(
                    select(WebhookDelivery).where(WebhookDelivery.delivery_id == job.delivery_id)
                )
            ).scalar_one_or_none()
            if deliv is None:
                log.warning("job.payload_missing", delivery_id=job.delivery_id)
                return
            # Phase 1: mark as processed (full PR upsert in Phase 2)
            await session.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == deliv.id)
                .values(processed=True, processed_at=func.now())
            )
            log.info("job_processed", delivery_id=job.delivery_id)

    await consume_loop(redis, session_factory, consumer_name, on_job=on_job)
