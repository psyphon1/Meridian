# ADR-006 — Phase 1: GitHub App + Webhook Ingestion Layer

**Status:** Accepted · **Date:** 2026-09-13

## Context

Phase 1 delivers the foundation of Meridian: a GitHub App that receives webhook events, persists them durably, and enqueues review jobs for the worker pipeline. This ADR consolidates all architectural decisions for Phase 1 into a single per-phase record. The detailed design specification lives in `docs/specs/2026-09-13-phase1-github-app-webhook-ingestion.md`.

## Decision Drivers

- GitHub's 10-second webhook response deadline must never be missed
- No phantom jobs (job in Redis without a corresponding DB payload row)
- At-least-once delivery semantics with idempotent consumers
- Redis unavailability must not take down webhook ingestion
- End-to-end distributed traces from webhook receipt to worker processing
- Industry-standard, machine-readable error responses

---

## D1 — Webhook Ingestion Architecture

**Decision:** The route handler (`apps/api/routers/webhooks.py`) is thin — it reads the raw request body via `await request.body()` (not a Pydantic model), extracts headers, and delegates all logic to a service function `packages/orchestration/ingestion.py:ingest_webhook(...)` which manages its own explicit DB transaction via `async with session.begin():`. The route handler maps the returned `IngestResult` to an HTTP status + error envelope.

**Rationale:** Raw body access is required for HMAC verification before JSON parsing. Thin handlers per `CODE_STANDARDS.md §1.1`. Explicit transaction scope ensures the advisory lock is released on commit/rollback, not on FastAPI dependency teardown.

**Idempotency:** Three layers — (1) `webhook_deliveries.delivery_id` unique constraint, (2) advisory lock via `pg_advisory_xact_lock(hashtextextended(repo_id || ':' || pr_number || ':' || head_sha, 0))`, (3) second check on `review_runs(pull_request_id, head_sha)` for an existing RECEIVED run (prevents duplicate review runs on GitHub redelivery with a new delivery_id).

---

## D2 — Transactional Outbox Pattern

**Decision:** The handler writes only to PostgreSQL (`webhook_deliveries` row with `enqueued = false`), commits, and returns 200. A separate outbox publisher coroutine in the worker process polls `WHERE enqueued = false FOR UPDATE SKIP LOCKED LIMIT 100`, calls `XADD` to Redis Streams, and marks `enqueued = true`. The `webhook_deliveries` table doubles as the outbox — no separate outbox table.

**Rationale:** Eliminates the dual-write hazard (XADD inside DB transaction). Decouples Redis availability from the 10-second webhook critical path. If Redis is down, webhooks are still accepted and persisted; the publisher catches up when Redis recovers. `FOR UPDATE SKIP LOCKED` partitions work across worker instances.

**Research:** AWS Prescriptive Guidance — transactional outbox pattern; microservices.io — transactional outbox.

---

## D3 — Redis Streams Priority Lanes

**Decision:** Three separate Redis Streams per priority tier: `meridian:reviews:high`, `meridian:reviews:medium`, `meridian:reviews:low`. The consumer reads high → medium → low, providing true priority semantics.

**Rationale:** A single stream with priority fields requires client-side sorting. Separate streams give Redis-native priority ordering.

---

## D4 — Database Schema Design

**Decision:** All 14 tables created upfront (13 core + `webhook_deliveries`). BIGSERIAL primary keys, pgvector extension for embeddings. Audit events use a PostgreSQL `SEQUENCE` (`audit_events_seq`) via `nextval()` for `sequence_number` — atomic, non-blocking; gaps on rollback are acceptable (hash-chain integrity depends on `previous_hash → current_hash` linking, not contiguous numbering).

**Rationale:** Avoids migration churn later; empty tables are cheap; FK relationships are correct from day 1. SEQUENCE is safer than `MAX+1` under concurrent inserts.

---

## D5 — GitHub Adapter Pattern

**Decision:** JWT minted from App private key (RS256). Installation tokens cached via a two-layer cache: L1 in-memory (per-process, ~60s TTL) + L2 Redis (shared across all processes, ~55s TTL). Invalidation propagates via Redis `DEL`. Rate-limit-aware `httpx.AsyncClient` with `X-RateLimit-Remaining` tracking.

**Rationale:** L1 avoids Redis round-trips for hot tokens; L2 shares tokens across all processes (API + workers). No direct GitHub API calls outside the `packages/github/` adapter (per `PROJECT_STRUCTURE.md` dependency rules).

---

## D6 — Worker Consumer Design

**Decision:** `XREADGROUP` with at-least-once delivery semantics. `XAUTOCLAIM` janitor reclaims pending entries older than a visibility timeout. Dead-letter after 3 failed attempts. `XACK` is called only after DB commit — crash before ack means redelivery, and consumer idempotency prevents duplicates.

**Rationale:** At-least-once + idempotent consumers = effectively exactly-once. The janitor prevents stuck entries from blocking the consumer group.



## D7 — Stripe-Style Error Envelope

**Decision:** All API errors follow a Stripe-style structured envelope: `{ "error": { "type": "...", "code": "...", "message": "...", "param": "...", "request_id": "...", "doc_url": "..." } }`. `type` is the broad category (`webhook`, `auth`, `rate_limit`, `validation`, `internal`); `code` is the specific machine-readable string (namespaced, e.g., `webhook.signature_invalid`). Webhook signature verification returns 401 (GitHub convention: bad signatures are auth failures, not malformed requests — deliberate deviation from Stripe's 400).

**Codified webhook error codes:** `webhook.signature_missing` (400), `webhook.signature_invalid` (401), `webhook.event_ignored` (200), `webhook.payload_invalid` (400), `webhook.idempotent_replay` (200), `webhook.duplicate_pr_sha` (200), `internal_error` (500).

**Rationale:** Machine-readable taxonomy; dual-level type+code matches industry standard; `request_id` enables trace correlation; `doc_url` enables consumer self-service. Updates `CODE_STANDARDS.md §3` in the same change set.

**Research:** Stripe API — error envelope structure and webhook signature verification HTTP status codes.

---

## D8 — Trace Context Propagation via JobMessage

**Decision:** A single W3C `traceparent` string (`00-<trace-id>-<span-id>-<flags>`) is carried in the `JobMessage` Pydantic schema as `traceparent: str | None`. The outbox publisher injects the current span context via `opentelemetry.propagate.inject()`; the worker extracts it via `opentelemetry.propagate.extract()` and creates child spans.

**Rationale:** End-to-end distributed traces with correct parent-child span relationships across the Redis Streams process boundary. Standard W3C format; no Redis-specific OTel dependency; `traceparent` is visible/inspectable in stream entries for debugging.

---

## Consequences

- **Positive:** Redis is fully decoupled from webhook ingestion; no phantom jobs; at-least-once delivery with idempotent consumers; end-to-end traces; industry-standard error responses.
- **Negative:** ~1s additional latency between webhook receipt and job enqueue (poll interval). Accepted — can be reduced if latency-sensitive workloads emerge.
- **Negative:** Worker process has two responsibilities (consumer + publisher). Accepted — both use the same Redis + DB connections; graceful drain handles both on SIGTERM.
- **Negative:** `CODE_STANDARDS.md §3` envelope change affects all endpoints. Accepted — doing it once prevents inconsistency.

## References

- Design spec: `docs/specs/2026-09-13-phase1-github-app-webhook-ingestion.md`
- `CODE_STANDARDS.md §3` (error envelope)
- `OBSERVABILITY.md §3` (trace propagation)
- `SECURITY.md §1` (trust hierarchy — webhook payloads are untrusted data)
