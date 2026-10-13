"""Integration tests for the ingestion service (Task 22) on real PostgreSQL.

Needs PG (advisory locks + JSONB). Uses the `pg_engine` fixture
(tests/integration/conftest.py) which skips cleanly when PG is unreachable.
"""

import asyncio
import json

import pytest
from packages.models.audit import WebhookDelivery
from packages.models.base import ReviewStatus
from packages.models.identity import Installation
from packages.models.repository import Repository
from packages.models.review import PullRequest, ReviewRun
from packages.orchestration.errors import WebhookPayloadError
from packages.orchestration.ingestion import ingest_webhook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.integration


def pr_payload(sha: str = "abc123", number: int = 42, repo_id: int = 67890) -> bytes:
    return json.dumps(
        {
            "action": "opened",
            "number": number,
            "installation": {"id": 12345},
            "repository": {"id": repo_id, "full_name": "owner/repo"},
            "pull_request": {
                "number": number,
                "title": "Add X",
                "head": {"sha": sha},
                "base": {"sha": "def789"},
            },
        }
    ).encode()


PAYLOAD = pr_payload()


@pytest.fixture
def factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False)


async def _count(factory) -> int:
    async with factory() as s:
        return (await s.execute(select(func.count()).select_from(WebhookDelivery))).scalar_one()


async def test_ingest_creates_delivery(factory):
    async with factory() as session, session.begin():
        result = await ingest_webhook(session, "delivery-uuid-1", "pull_request", "opened", PAYLOAD)
    assert result.status == "accepted"
    assert result.delivery_id == "delivery-uuid-1"

    async with factory() as session:
        deliv = (
            await session.execute(
                select(WebhookDelivery).where(WebhookDelivery.delivery_id == "delivery-uuid-1")
            )
        ).scalar_one()
        assert deliv.event == "pull_request"
        assert deliv.enqueued is False
        assert deliv.payload["pull_request"]["head"]["sha"] == "abc123"
        assert deliv.payload_size_bytes == len(PAYLOAD)


async def test_ingest_idempotent_replay(factory):
    async with factory() as s, s.begin():
        r1 = await ingest_webhook(s, "dup-1", "pull_request", "opened", PAYLOAD)
    async with factory() as s, s.begin():
        r2 = await ingest_webhook(s, "dup-1", "pull_request", "opened", PAYLOAD)
    assert (r1.status, r2.status) == ("accepted", "replayed")
    assert await _count(factory) == 1


async def test_concurrent_same_delivery_is_serialised_by_advisory_lock(factory):
    async def one() -> str:
        async with factory() as s, s.begin():
            return (await ingest_webhook(s, "race-1", "pull_request", "opened", PAYLOAD)).status

    statuses = sorted(await asyncio.gather(one(), one(), one()))
    assert statuses == ["accepted", "replayed", "replayed"]
    assert await _count(factory) == 1


async def test_installation_event_is_ingested(factory):
    body = json.dumps({"action": "created", "installation": {"id": 5, "account": {"login": "o"}}})
    async with factory() as s, s.begin():
        r = await ingest_webhook(s, "inst-1", "installation", "created", body.encode())
        again = await ingest_webhook(s, "inst-1", "installation", "created", body.encode())
    assert (r.status, again.status) == ("accepted", "replayed")


async def test_installation_repositories_event_is_ingested(factory):
    body = json.dumps(
        {
            "action": "added",
            "installation": {"id": 5},
            "repositories_added": [{"id": 1, "full_name": "o/r"}],
        }
    ).encode()
    async with factory() as s, s.begin():
        r = await ingest_webhook(s, "instrepo-1", "installation_repositories", "added", body)
    assert r.status == "accepted"
    async with factory() as s:
        row = (await s.execute(select(WebhookDelivery))).scalar_one()
        assert row.event == "installation_repositories"


async def test_invalid_payload_writes_nothing(factory):
    async with factory() as s:
        with pytest.raises(WebhookPayloadError):
            async with s.begin():
                await ingest_webhook(s, "bad-1", "pull_request", "opened", b'{"action":"opened"}')
    assert await _count(factory) == 0


async def test_ignored_event_writes_nothing(factory):
    async with factory() as s, s.begin():
        r = await ingest_webhook(s, "ign-1", "pull_request", "closed", PAYLOAD)
    assert r.status == "ignored"
    assert await _count(factory) == 0


async def _seed_received_run(factory, sha: str, status: ReviewStatus = ReviewStatus.RECEIVED):
    async with factory() as s, s.begin():
        inst = Installation(
            github_installation_id=12345, account_login="owner", account_type="User"
        )
        s.add(inst)
        await s.flush()
        repo = Repository(
            installation_id=inst.id,
            github_repo_id=67890,
            owner="owner",
            name="repo",
            full_name="owner/repo",
        )
        s.add(repo)
        await s.flush()
        pr = PullRequest(
            repository_id=repo.id, github_pr_number=42, head_sha=sha, base_sha="def789"
        )
        s.add(pr)
        await s.flush()
        s.add(ReviewRun(pull_request_id=pr.id, status=status))


async def test_layer3_duplicate_pr_sha_with_new_delivery_id_is_replayed(factory):
    await _seed_received_run(factory, "abc123")
    async with factory() as s, s.begin():
        r = await ingest_webhook(s, "fresh-delivery", "pull_request", "synchronize", PAYLOAD)
    assert r.status == "replayed"
    assert await _count(factory) == 0  # no new outbox row, no new run


async def test_layer3_new_head_sha_is_accepted(factory):
    await _seed_received_run(factory, "abc123")
    async with factory() as s, s.begin():
        r = await ingest_webhook(
            s, "new-sha", "pull_request", "synchronize", pr_payload(sha="ffff999")
        )
    assert r.status == "accepted"


async def test_layer3_ignores_non_received_runs(factory):
    await _seed_received_run(factory, "abc123", status=ReviewStatus.COMPLETED)
    async with factory() as s, s.begin():
        r = await ingest_webhook(s, "after-complete", "pull_request", "reopened", PAYLOAD)
    assert r.status == "accepted"
