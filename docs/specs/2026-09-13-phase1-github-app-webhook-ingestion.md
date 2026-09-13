# Meridian — Phase 1 Design Spec
# GitHub App + Webhook Ingestion Layer

---
Created: 2026-09-13
Author: Chinmay Duse (psyphon1)
Version: 1.1.0
Last Updated: 2026-09-13
Status: accepted
---

**Owner:** Chinmay Duse (psyphon1)
**Phase:** 1 — Platform
**Source of truth:** [`Meridian_Design_Doc_Final.html`](Meridian_Design_Doc_Final.html) §52 (V1 Implementation Boundaries)

---

## 1. Scope

### In Scope

| Component | Description |
|---|---|
| GitHub App | App private key JWT generation, installation token caching, webhook secret verification |
| Webhook Ingestion | FastAPI endpoint receiving GitHub webhooks: HMAC verify → idempotency check → persist → enqueue → ack within 10s |
| FastAPI API | App factory, lifespan management, health/readiness endpoints, dependency injection |
| PostgreSQL Schema | All 13 core entities + `webhook_deliveries` table, SQLAlchemy 2.0 async models, Alembic initial migration |
| Redis Streams | 3 priority streams (high/medium/low) + dead-letter stream, consumer groups, XADD/XREADGROUP/XACK/XAUTOCLAIM/XTRIM |
| Worker | Async consumer process: reads priority streams, upserts DB records, creates `review_run` in RECEIVED state |
| Observability | structlog structured logging, OpenTelemetry tracing setup |
| Tests | Unit + integration + mocked e2e |

### Out of Scope (Documented as Remaining)

| Component | Phase |
|---|---|
| GitHub OAuth App (dashboard sign-in) | Phase 1+ (deferred) |
| Review publishing (post comments/reviews back to GitHub) | Phase 3 (with agents) |
| LangGraph orchestrator / review state machine | Phase 3 |
| Risk engine / intent analysis | Phase 3 |
| Repository indexing / code intelligence | Phase 2 |
| BYOK / KMS envelope encryption | Phase 5 |
| Sandbox execution | Phase 4 |
| Next.js web dashboard | Phase 5+ |

### Key Constraint

GitHub enforces a **10-second response window** on webhook deliveries. The ingestion endpoint must verify the signature, check idempotency, persist the delivery, enqueue the job, and return `2xx` — all within 10 seconds. All real work happens in the worker via Redis Streams, never inline.

---

## 2. Architecture

### 2.1 Approach: Thin Apps + Capability Packages

```
apps/api/          → FastAPI app (lifespan, routers, DI) — thin, delegates to packages
apps/worker/       → Consumer process (reads streams, persists, marks RECEIVED)
packages/config/   → Settings (pydantic-settings), DB engine, Redis client
packages/models/   → SQLAlchemy 2.0 ORM models (all 13 tables) + Pydantic schemas
packages/github/   → GitHub adapter: JWT gen, installation tokens, webhook verify, API client
packages/orchestration/ → Redis Streams producer + consumer + stream config
packages/observability/ → structlog config, OTel setup
packages/security/ → HMAC verification, advisory lock helpers
```

### 2.2 Dependency Graph

```
apps/api → packages/config, packages/github, packages/orchestration,
           packages/models, packages/observability, packages/security

apps/worker → packages/config, packages/models, packages/orchestration,
              packages/observability, packages/security

packages/github → packages/config, packages/observability
packages/orchestration → packages/config, packages/models, packages/observability
packages/models → packages/config
packages/security → packages/config
```

**Rules enforced:**
- No business logic in route handlers — handlers validate and delegate only.
- No raw GitHub API calls outside `packages/github/`.
- No direct Redis calls outside `packages/orchestration/`.
- Apps depend on packages; packages depend on lower-level packages; no circular deps.

---

## 3. Module Map

### 3.1 `apps/api/`

```
apps/api/
├── __init__.py
├── main.py                # FastAPI app factory + lifespan (startup/shutdown)
├── deps.py                # DI: get_db_session, get_redis, get_github_client
└── routers/
    ├── __init__.py
    ├── health.py          # GET /v1/health, GET /v1/ready
    └── webhooks.py        # POST /v1/webhooks/github
```

### 3.2 `apps/worker/`

```
apps/worker/
├── __init__.py
├── main.py                # Entrypoint: asyncio.run, signal handling, graceful drain
├── consumer.py            # XREADGROUP loop, priority ordering, idempotent processing, XACK
├── outbox_publisher.py    # Polls webhook_deliveries WHERE enqueued=false (SKIP LOCKED), XADD, mark enqueued
└── janitor.py             # XAUTOCLAIM stalled entries, dead-letter, XTRIM
```

### 3.3 `packages/config/`

```
packages/config/
├── __init__.py
├── settings.py            # pydantic-settings: all env vars typed + validated
├── database.py            # async SQLAlchemy engine + async_sessionmaker
└── redis.py               # async Redis client factory + stream name constants
```

### 3.4 `packages/models/`

```
packages/models/
├── __init__.py
├── base.py                # DeclarativeBase, naming convention, TimestampMixin
├── enums.py               # ReviewStatus, Severity, RiskTier, EventType, etc.
├── user.py                # User, APIKey
├── installation.py        # Installation
├── repository.py          # Repository, Commit, File, CodeSymbol
├── pull_request.py        # PullRequest
├── review.py              # ReviewRun, Finding, Evidence, ToolRun
├── memory.py              # ReviewMemory
├── audit.py               # AuditEvent (append-only, hash-chained)
├── webhook.py             # WebhookDelivery (idempotency table)
└── schemas.py             # Pydantic v2: webhook payload models, job message, API responses
```

### 3.5 `packages/github/`

```
packages/github/
├── __init__.py
├── client.py              # httpx AsyncClient wrapper (typed API methods)
├── auth.py                # App JWT generation + InstallationTokenCache
├── webhooks.py            # HMAC-SHA256 verification, event/action extraction
├── errors.py              # GitHubError hierarchy
└── types.py               # TypedDict/Pydantic models for GitHub webhook payloads
```

### 3.6 `packages/orchestration/`

```
packages/orchestration/
├── __init__.py
├── ingestion.py           # ingest_webhook() service function: verify → advisory lock → idempotency → persist outbox row → commit
├── producer.py            # XADD to priority streams (called by outbox publisher)
├── consumer.py            # XREADGROUP, consumer group management
├── streams.py             # Stream name constants, dead-letter, XTRIM config
└── messages.py            # JobMessage Pydantic schema (serialized as JSON in stream, includes traceparent)
```

### 3.7 `packages/observability/`

```
packages/observability/
├── __init__.py
├── logging.py             # structlog config (JSON, redaction, correlation IDs)
└── tracing.py             # OpenTelemetry tracer setup
```

### 3.8 `packages/security/`

```
packages/security/
├── __init__.py
├── hmac_verify.py         # Timing-safe HMAC-SHA256 verification
└── advisory_lock.py       # PostgreSQL advisory lock helpers
```

---

## 4. Webhook Handler Flow

> **Architecture note — Transactional Outbox (ADR-006):** The original design performed `XADD` to Redis *inside* the DB transaction (a dual-write). This couples webhook availability to Redis health: if Redis is down, every webhook returns 500 and GitHub eventually stops retrying. The revised flow uses the **transactional outbox pattern**: the handler writes only to PostgreSQL (the `webhook_deliveries` row doubles as the outbox with `enqueued = false`), commits, and returns 200. A separate outbox publisher coroutine in the worker process polls for `enqueued = false` rows, calls `XADD`, and marks `enqueued = true`. This decouples Redis from the 10-second critical path. See ADR-006.

### 4.1 Step-by-Step

The route handler (`apps/api/routers/webhooks.py`) is **thin**: it reads the raw request, extracts headers, and delegates all logic to a service function `packages/orchestration/ingestion.py:ingest_webhook(...)` which manages its own explicit DB transaction via `async with session.begin():`. The route handler maps the returned `IngestResult` to an HTTP status + error envelope. No business logic in the route (per `CODE_STANDARDS.md §1.1`).

```
POST /v1/webhooks/github arrives
  │
  ├─ 1. Read raw body + headers via `await request.body()` (do NOT parse JSON yet)
  │     — FastAPI route param is `request: Request`, not a Pydantic model, to access raw bytes
  ├─ 2. Extract headers: X-Hub-Signature-256, X-GitHub-Event, X-GitHub-Delivery
  │     └─ Missing X-Hub-Signature-256 → 400 {"error": {"type":"webhook","code":"webhook.signature_missing",...}}
  ├─ 3. Verify HMAC-SHA256(raw_body, webhook_secret) — timing-safe compare
  │     └─ FAIL → 401 {"error": {"type":"webhook","code":"webhook.signature_invalid",...}}
  │        (401 not 400: GitHub treats bad signatures as auth failures; log: signature_verify_failed, delivery_id)
  ├─ 4. Event/action filter:
  │     ├─ X-GitHub-Event in {pull_request, installation, installation_repositories}?
  │     └─ Action in allowed set for that event?
  │     └─ NO → 200 {"status":"ignored"} (fast reject, no DB write, no Redis)
  ├─ 5. Parse JSON body → typed Pydantic model (per event type)
  │     └─ Parse error → 400 {"error": {"type":"webhook","code":"webhook.payload_invalid",...}}
  ├─ 6. Delegate to service: ingest_webhook(raw_body, headers, payload_model) → IngestResult
  │     Inside the service's explicit `async with session.begin():` transaction:
  │     ├─ a. pg_advisory_xact_lock(hashtextextended(repo_id || ':' || pr_number || ':' || head_sha, 0))
  │     │     — 64-bit BIGINT lock key; collisions astronomically rare (ADR-006)
  │     ├─ b. Check webhook_deliveries for X-GitHub-Delivery — if exists → 200 (idempotent replay)
  │     ├─ c. SECOND idempotency check: query review_runs for existing RECEIVED run on
  │     │     (pull_request_id, head_sha) — if exists → 200 (duplicate_pr_sha_replay, no new run)
  │     ├─ d. Insert webhook_delivery (delivery_id, event, action, payload, payload_size_bytes, enqueued=false)
  │     ├─ e. Commit transaction (releases advisory lock) — Redis is NOT in the critical path
  │     └─ f. Return IngestResult(status="accepted", delivery_id=...)
  ├─ 7. Route handler maps IngestResult → 200 response
  └─ Error: any exception → 500 {"error":{"type":"internal","code":"internal_error",...}},
           structured log, transaction rollback (no partial state — outbox row not committed)
```

**Why the transactional outbox matters:** With the dual-write approach, if `XADD` succeeds but the DB commit fails (connection drop), a phantom job exists in Redis with no payload row — the worker fails permanently. Conversely, if Redis is down, `XADD` throws, the transaction rolls back, and GitHub sees 500s until it exhausts retries (~24h). The outbox pattern eliminates both failure modes: the handler's only external dependency is PostgreSQL.

### 4.2 Outbox Publisher (in worker process — ADR-006)

A coroutine started alongside the consumer loop in the worker process:

```
outbox_publisher_loop (every ~1s):
  ├─ SELECT id, delivery_id, event, action, installation_id, repository_id,
  │         repository_full_name, pr_number, pr_title, head_sha, base_sha
  │  FROM webhook_deliveries
  │  WHERE enqueued = false
  │  ORDER BY created_at
  │  LIMIT 100
  │  FOR UPDATE SKIP LOCKED          ← partitions work across worker instances
  ├─ For each row:
  │    ├─ Build JobMessage (reference, not full payload) + inject traceparent
  │    ├─ XADD to meridian:reviews:{priority} stream
  │    └─ UPDATE webhook_deliveries SET enqueued = true, enqueued_at = now() WHERE id = ?
  ├─ Commit the SKIP LOCKED transaction
  └─ If no rows found: asyncio.sleep(1) then retry
```

`FOR UPDATE SKIP LOCKED` ensures multiple worker instances don't claim the same rows. The publisher runs in the worker process (not the API process) so that API scaling doesn't multiply publishers unpredictably and so that ingestion is fully decoupled from Redis availability.

### 4.2 Allowed Events & Actions

| Event | Allowed Actions |
|---|---|
| `pull_request` | `opened`, `synchronize`, `reopened`, `edited` |
| `installation` | `created`, `deleted`, `new_permissions_accepted` |
| `installation_repositories` | `added`, `removed` |

### 4.3 Job Message Schema

```json
{
  "delivery_id": "uuid-from-github",
  "event": "pull_request",
  "action": "opened",
  "installation_id": 12345,
  "repository_id": 67890,
  "repository_full_name": "owner/repo",
  "pr_number": 42,
  "pr_title": "Add feature X",
  "head_sha": "abc123def456",
  "base_sha": "def789ghi012",
  "priority": "medium",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
  "enqueued_at": "2026-09-13T12:00:00Z"
}
```

The job message is a **reference**, not the full payload. The worker reads the full payload from the `webhook_deliveries` table by `delivery_id`. This keeps stream entries small and avoids duplicating large diffs in Redis.

**`traceparent` field (ADR-006):** A single W3C traceparent string (`00-<trace-id>-<span-id>-<flags>`) carrying the OpenTelemetry trace context from the API process to the worker process. The outbox publisher injects the current span context via `opentelemetry.propagate.inject()`; the worker extracts it via `opentelemetry.propagate.extract()` and creates child spans. This preserves the parent-child span relationship across the Redis Streams process boundary, giving end-to-end distributed traces for `webhook.receive → worker.process`. The field is `str | None` (nullable for cases where no active span exists, e.g., tests).

---

## 5. Database Schema

### 5.1 Tables (14 total: 13 core + 1 ingestion)

All tables use `TIMESTAMP WITH TIME ZONE` for timestamps. Primary keys are `BIGSERIAL` (BigInt). The `TimestampMixin` adds `created_at` and `updated_at` to applicable tables.

#### `users`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| github_id | BIGINT | UNIQUE, NOT NULL |
| username | VARCHAR(255) | NOT NULL |
| email | VARCHAR(255) | nullable |
| avatar_url | TEXT | nullable |
| created_at, updated_at | TIMESTAMPTZ | mixin |

#### `api_keys`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| user_id | BIGINT FK→users | NOT NULL |
| provider | VARCHAR(50) | NOT NULL |
| encrypted_key | BYTEA | NOT NULL (envelope-encrypted, Phase 5) |
| is_active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMPTZ | |
| rotated_at | TIMESTAMPTZ | nullable |

#### `installations`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| github_installation_id | BIGINT | UNIQUE, NOT NULL |
| account_login | VARCHAR(255) | NOT NULL |
| account_type | VARCHAR(50) | NOT NULL (User/Organization) |
| status | VARCHAR(20) | NOT NULL (active/uninstalled) |
| user_id | BIGINT FK→users | nullable |
| created_at, updated_at | TIMESTAMPTZ | mixin |

#### `repositories`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| installation_id | BIGINT FK→installations | NOT NULL |
| github_repo_id | BIGINT | UNIQUE, NOT NULL |
| owner | VARCHAR(255) | NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| full_name | VARCHAR(512) | NOT NULL |
| default_branch | VARCHAR(255) | nullable |
| is_private | BOOLEAN | DEFAULT false |
| created_at, updated_at | TIMESTAMPTZ | mixin |

#### `commits`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| repository_id | BIGINT FK→repositories | NOT NULL |
| sha | VARCHAR(40) | NOT NULL |
| message | TEXT | nullable |
| author | VARCHAR(255) | nullable |
| authored_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |

#### `files`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| repository_id | BIGINT FK→repositories | NOT NULL |
| path | TEXT | NOT NULL |
| language | VARCHAR(50) | nullable |
| size | INTEGER | nullable |
| last_commit_sha | VARCHAR(40) | nullable |
| created_at, updated_at | TIMESTAMPTZ | mixin |

#### `code_symbols`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| file_id | BIGINT FK→files | NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| kind | VARCHAR(50) | NOT NULL (function/class/method) |
| start_line | INTEGER | NOT NULL |
| end_line | INTEGER | NOT NULL |
| signature | TEXT | nullable |
| embedding | vector(1536) | pgvector, nullable (Phase 2) |
| created_at | TIMESTAMPTZ | |

#### `pull_requests`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| repository_id | BIGINT FK→repositories | NOT NULL |
| github_pr_number | INTEGER | NOT NULL |
| title | TEXT | nullable |
| body | TEXT | nullable |
| head_sha | VARCHAR(40) | NOT NULL |
| base_sha | VARCHAR(40) | NOT NULL |
| author | VARCHAR(255) | nullable |
| state | VARCHAR(20) | NOT NULL (open/closed) |
| created_at, updated_at | TIMESTAMPTZ | mixin |
| | | UNIQUE(repository_id, github_pr_number) |

#### `review_runs`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| pull_request_id | BIGINT FK→pull_requests | NOT NULL |
| status | VARCHAR(30) | NOT NULL (enum: RECEIVED→COMPLETED) |
| risk_tier | VARCHAR(10) | nullable (LOW/MEDIUM/HIGH/CRITICAL) |
| started_at | TIMESTAMPTZ | nullable |
| completed_at | TIMESTAMPTZ | nullable |
| error_message | TEXT | nullable |
| created_at, updated_at | TIMESTAMPTZ | mixin |

#### `findings`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| review_run_id | BIGINT FK→review_runs | NOT NULL |
| category | VARCHAR(50) | NOT NULL |
| severity | VARCHAR(10) | NOT NULL (BLOCKING/HIGH/MEDIUM/LOW/NIT) |
| confidence | REAL | NOT NULL (0.0–1.0) |
| file_path | TEXT | NOT NULL |
| start_line | INTEGER | NOT NULL |
| end_line | INTEGER | NOT NULL |
| message | TEXT | NOT NULL |
| evidence_id | BIGINT FK→evidence | nullable |
| created_at | TIMESTAMPTZ | |

#### `evidence`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| review_run_id | BIGINT FK→review_runs | NOT NULL |
| type | VARCHAR(30) | NOT NULL (tool_run/test_execution/sha_pinned_code_span) |
| artifact_ref | TEXT | NOT NULL |
| summary | TEXT | nullable |
| verified | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | |

#### `tool_runs`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| review_run_id | BIGINT FK→review_runs | NOT NULL |
| tool_name | VARCHAR(50) | NOT NULL (semgrep/codeql/sandbox) |
| status | VARCHAR(20) | NOT NULL |
| output_ref | TEXT | nullable |
| duration_ms | INTEGER | nullable |
| created_at | TIMESTAMPTZ | |

#### `review_memory`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| repository_id | BIGINT FK→repositories | NOT NULL |
| key | VARCHAR(255) | NOT NULL |
| value | JSONB | NOT NULL |
| created_at, updated_at | TIMESTAMPTZ | mixin |

#### `audit_events` (append-only, hash-chained)
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| sequence_number | BIGINT | NOT NULL, UNIQUE |
| previous_hash | VARCHAR(64) | NOT NULL |
| current_hash | VARCHAR(64) | NOT NULL |
| event_type | VARCHAR(50) | NOT NULL |
| actor | VARCHAR(255) | nullable |
| ip | VARCHAR(45) | nullable |
| payload | JSONB | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Hash chain: `current_hash = SHA256(previous_hash || event_type || actor || payload || created_at)`. The first row has `previous_hash = "0" * 64`.

**Sequence allocation (ADR-006):** `sequence_number` is populated by a PostgreSQL `SEQUENCE` (`audit_events_seq`) via `nextval()` before insert. Sequences are atomic and non-blocking under concurrent inserts. Gaps may appear on transaction rollback (the sequence value is consumed but the row never commits) — this is acceptable because hash-chain integrity depends on correct `previous_hash → current_hash` linking, not on contiguous numbering. The `sequence_number` column is `UNIQUE NOT NULL` (not necessarily contiguous).

#### `webhook_deliveries` (idempotency + outbox table — not in original 13)
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| delivery_id | VARCHAR(255) | UNIQUE, NOT NULL (X-GitHub-Delivery) |
| event | VARCHAR(50) | NOT NULL |
| action | VARCHAR(50) | NOT NULL |
| payload | JSONB | NOT NULL (full webhook payload; PostgreSQL TOAST handles large values) |
| payload_size_bytes | INTEGER | NOT NULL (size of raw payload for monitoring/alerting on oversized webhooks) |
| processed | BOOLEAN | DEFAULT false (set true by worker after review_run created) |
| processed_at | TIMESTAMPTZ | nullable |
| enqueued | BOOLEAN | DEFAULT false (outbox flag — set true by outbox publisher after XADD) |
| enqueued_at | TIMESTAMPTZ | nullable (set when XADD succeeds) |
| created_at | TIMESTAMPTZ | |

This table serves **double duty** as both the idempotency key store and the transactional outbox (ADR-006). The webhook handler inserts a row with `enqueued = false`; the outbox publisher coroutine polls `WHERE enqueued = false FOR UPDATE SKIP LOCKED`, calls `XADD` to Redis, then sets `enqueued = true`. No separate outbox table is needed.

### 5.2 Indexes

| Table | Index |
|---|---|
| pull_requests | UNIQUE(repository_id, github_pr_number) |
| repositories | UNIQUE(github_repo_id) |
| installations | UNIQUE(github_installation_id) |
| webhook_deliveries | UNIQUE(delivery_id), INDEX(enqueued) WHERE enqueued = false (outbox publisher hot path) |
| review_runs | INDEX(pull_request_id), INDEX(status), INDEX(pull_request_id, head_sha) (second idempotency check — ADR-006) |
| findings | INDEX(review_run_id), INDEX(severity) |
| audit_events | UNIQUE(sequence_number), INDEX(event_type) |
| code_symbols | INDEX(file_id), HNSW vector index on embedding (Phase 2) |

### 5.3 Alembic Migration

- `db/migrations/` — Alembic environment configured for async SQLAlchemy
- `db/migrations/env.py` — imports all models from `packages/models/` for autogenerate
- Initial migration: `001_initial_schema.py` — creates all 14 tables + indexes + pgvector extension
- `db/schema/` — kept as documentation reference (generated from migration, never hand-edited)

---

## 6. GitHub Adapter

### 6.1 JWT Generation (`packages/github/auth.py`)

```python
def generate_app_jwt(private_key: str, app_id: int) -> str:
    """Generate a GitHub App JWT (RS256, 10-minute expiry)."""
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")
```

- `iat` is set 60 seconds in the past to tolerate clock skew
- `exp` is 10 minutes (GitHub's maximum)
- `iss` is the App ID

### 6.2 Installation Token Cache

```python
class InstallationTokenCache:
    """Two-layer (L1 in-memory + L2 Redis) shared cache of installation access tokens."""

    _local: dict[int, tuple[str, float]]  # installation_id → (token, expires_at)
    _redis: Redis

    async def get_token(self, installation_id: int) -> str:
        # 1. Check L1 (in-process dict) — fast path, no network
        # 2. Check L2 (Redis key: meridian:install_token:{id}, TTL = expiry - 60s)
        # 3. Cache miss → fetch from GitHub API, write to both L1 and L2

    async def invalidate(self, installation_id: int) -> None:
        # DEL Redis key (propagates to all processes)
        # Clear local L1 entry
        # Called on 401 response
```

- **L1**: per-process in-memory dict — avoids Redis round-trip for hot tokens (<1μs lookup)
- **L2**: Redis `SET meridian:install_token:{installation_id} <token> EX <ttl>` where `ttl = expiry - 60s` safety margin — shared across all API + worker processes
- On 401 from any GitHub API call: `invalidate()` deletes the Redis key (so all processes see the invalidation) and clears the local L1 entry, then regenerates and retries once
- Cache coherence: L1 entries have the same expiry as the L2 TTL; a local TTL check evicts stale L1 entries without a Redis call
- All processes (API + workers) share the same Redis-backed L2 cache, eliminating redundant GitHub token fetches across process boundaries (ADR-006)

### 6.3 Webhook Verification (`packages/github/webhooks.py`)

```python
def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-Hub-Signature-256 header using timing-safe comparison."""
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

- Uses `hmac.compare_digest()` to prevent timing attacks
- Expected format: `sha256=<hex_digest>`
- Returns `False` on any mismatch (never raises — caller decides status code)

### 6.4 API Client (`packages/github/client.py`)

```python
class GitHubClient:
    """Typed async GitHub API client with rate-limit awareness."""
    
    async def get_installation_token(self, installation_id: int) -> str: ...
    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[PRFile]: ...
    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str: ...
    async def post_review(self, owner: str, repo: str, pr_number: int, review: ReviewPayload) -> None: ...
    async def post_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None: ...
```

- Uses `httpx.AsyncClient`
- Per-installation token bucket rate limiting
- Honors `X-RateLimit-Remaining`, `Retry-After` headers
- On 429/403 with `Retry-After`: exponential backoff with jitter, max 3 retries
- All methods return typed Pydantic models

### 6.5 Error Hierarchy (`packages/github/errors.py`)

```
MeridianError (base)
  └── GitHubError
        ├── AuthenticationError (401)
        ├── RateLimitError (429, 403 with Retry-After)
        ├── NotFoundError (404)
        ├── ValidationError (422)
        └── ServerError (5xx)
```

---

## 7. Redis Streams Design

### 7.1 Streams

| Stream | Purpose |
|---|---|
| `meridian:reviews:high` | CRITICAL/HIGH risk jobs — consumed first |
| `meridian:reviews:medium` | MEDIUM risk jobs — consumed when high is empty (default in Phase 1) |
| `meridian:reviews:low` | LOW risk jobs — consumed when medium is empty |
| `meridian:reviews:deadletter` | Jobs that exceeded max retry attempts (3) |

### 7.2 Consumer Group

- Group name: `meridian-workers`
- Created on all 3 priority streams at worker startup (`XGROUP CREATE ... MKSTREAM`)
- One consumer per worker process (consumer name = hostname + PID)

### 7.3 Producer (`packages/orchestration/producer.py`)

```python
async def enqueue_job(redis: Redis, priority: str, job: JobMessage) -> str:
    """XADD a job message to the appropriate priority stream. Returns stream ID.

    Called by the outbox publisher (apps/worker/outbox_publisher.py), NOT by the
    webhook handler directly. This decouples Redis from the 10-second webhook
    critical path (ADR-006).
    """
    stream = f"meridian:reviews:{priority}"
    msg_id = await redis.xadd(stream, {"data": job.model_dump_json()})
    return msg_id
```

### 7.4 Consumer (`apps/worker/consumer.py`)

```python
async def consume_loop(redis: Redis, db_session_factory, consumer_name: str):
    """Main consumer loop — reads high → medium → low in priority order."""
    while running:
        for stream in [HIGH, MEDIUM, LOW]:
            messages = await redis.xreadgroup(
                groupname="meridian-workers",
                consumername=consumer_name,
                streams={stream: ">"},
                count=1,
                block=5000,
            )
            if messages:
                await process_message(messages, db_session_factory)
                break
```

### 7.5 Janitor (`apps/worker/janitor.py`)

```python
async def janitor_loop(redis: Redis):
    """Every 60s: XAUTOCLAIM stalled entries, move exhausted entries to dead-letter."""
    while running:
        for stream in [HIGH, MEDIUM, LOW]:
            claimed = await redis.xautoclaim(
                stream, "meridian-workers", consumer_name,
                min_idle_time=300_000
            )
            for entry_id, fields, attempt_count in claimed:
                if attempt_count >= 3:
                    await redis.xadd(DEADLETTER, fields)
                    await redis.xack(stream, "meridian-workers", entry_id)
        
        for stream in [HIGH, MEDIUM, LOW]:
            await redis.xtrim(stream, maxlen=10000)
        
        await asyncio.sleep(60)
```

### 7.6 Delivery Semantics

**Webhook → Redis (via outbox publisher):**
- The webhook handler writes only the `webhook_deliveries` outbox row (`enqueued = false`) and commits — this is the atomic step
- The outbox publisher polls `WHERE enqueued = false FOR UPDATE SKIP LOCKED`, calls `XADD`, then marks `enqueued = true` in the same transaction
- If the publisher crashes after `XADD` but before marking `enqueued = true`: the job is in Redis *and* the row is still `enqueued = false` → on restart, the publisher re-XADDs. The worker's idempotency check (`delivery_id` unique + `review_runs(pull_request_id, head_sha)` check) prevents duplicate review runs
- If Redis is down: the handler still returns 200 to GitHub; the publisher retries when Redis recovers. **Decoupled availability**

**Redis → Worker (consumer):**
- A message is only `XACK`'d **after** the DB transaction commits
- If the worker crashes before `XACK`: the message remains in the PEL
- On restart or janitor sweep: `XAUTOCLAIM` re-delivers the message
- The consumer is idempotent: `webhook_deliveries.delivery_id` unique constraint + second idempotency check on `review_runs(pull_request_id, head_sha)` prevents duplicates
- `XTRIM MAXLEN 10000` keeps streams bounded

---

## 8. Worker Flow

```
Worker starts
  ├─ Load settings (packages/config)
  ├─ Initialize structlog (packages/observability)
  ├─ Connect to Redis (packages/config/redis.py)
  ├─ Connect to PostgreSQL (packages/config/database.py)
  ├─ Ensure consumer groups exist (XGROUP CREATE ... MKSTREAM on all 3 streams)
  ├─ Start outbox_publisher coroutine (polls webhook_deliveries, XADD, marks enqueued)
  ├─ Start janitor coroutine
  ├─ Register signal handlers (SIGTERM → graceful drain)
  └─ Main consumer loop (XREADGROUP BLOCK 5000):
       ├─ Read from meridian:reviews:high (if messages)
       ├─ Read from meridian:reviews:medium (if high empty)
       ├─ Read from meridian:reviews:low (if medium empty)
       ├─ For each message:
       │    ├─ Parse JobMessage from stream fields
       │    ├─ Extract traceparent → set OTel span context (ADR-006)
       │    ├─ Fetch full webhook payload from webhook_deliveries by delivery_id
       │    ├─ DB transaction:
       │    │    ├─ Upsert installation (from payload)
       │    │    ├─ Upsert repository (from payload)
       │    │    ├─ Upsert pull_request (from payload)
       │    │    ├─ Create review_run (status=RECEIVED, risk_tier=MEDIUM)
       │    │    ├─ Insert audit_event (hash-chained, sequence via nextval(audit_events_seq))
       │    │    ├─ Mark webhook_delivery.processed = true
       │    │    └─ Commit
       │    ├─ XACK the message (after commit = at-least-once)
       │    └─ Log: job_processed {delivery_id, run_id, stream, duration_ms}
       └─ On SIGTERM: stop reading, finish current message, XACK, drain outbox publisher, drain janitor, exit 0
```

---

## 9. FastAPI App Structure

### 9.1 App Factory (`apps/api/main.py`)

```python
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Meridian API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health_router, prefix="/v1")
    app.include_router(webhooks_router, prefix="/v1")
    return app

async def lifespan(app: FastAPI):
    # Startup
    app.state.db_engine = create_async_engine(...)
    app.state.redis = Redis.from_url(...)
    app.state.github = GitHubClient(...)
    structlog.configure(...)
    yield
    # Shutdown
    await app.state.db_engine.dispose()
    await app.state.redis.aclose()
```

### 9.2 Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/health` | Liveness — always returns 200 |
| GET | `/v1/ready` | Readiness — checks DB + Redis connectivity |
| POST | `/v1/webhooks/github` | Webhook ingestion — verify, persist, enqueue, ack |

### 9.3 Error Envelope

All API errors follow a Stripe-style structured envelope (ADR-006, updating `CODE_STANDARDS.md §3`):
```json
{
  "error": {
    "type": "webhook",
    "code": "webhook.signature_invalid",
    "message": "Webhook signature verification failed.",
    "param": "X-Hub-Signature-256",
    "request_id": "req_01J...",
    "doc_url": "https://docs.meridian.dev/api/errors#webhook-signature-invalid"
  }
}
```

| Field | Purpose |
|---|---|
| `type` | Broad error category: `webhook`, `auth`, `rate_limit`, `validation`, `internal` |
| `code` | Machine-readable specific error (namespaced: `webhook.signature_invalid`, `webhook.event_ignored`, etc.) |
| `message` | Human-readable description (no secrets, no stack traces) |
| `param` | The input parameter that caused the error (e.g., `X-Hub-Signature-256`); `null` when not applicable |
| `request_id` | Correlation ID for tracing (maps to OTel trace ID / `X-GitHub-Delivery`) |
| `doc_url` | Link to error documentation (populated when docs exist; `null` otherwise) |

**Webhook error code taxonomy:**

| Code | HTTP | When |
|---|---|---|
| `webhook.signature_missing` | 400 | `X-Hub-Signature-256` header absent |
| `webhook.signature_invalid` | 401 | HMAC verification failed (401: auth failure per GitHub convention, not 400) |
| `webhook.event_ignored` | 200 | Event/action not in allowed set (success, not error — body: `{"status":"ignored"}`) |
| `webhook.payload_invalid` | 400 | JSON parse error or Pydantic validation failure |
| `webhook.idempotent_replay` | 200 | Same `delivery_id` already processed (success — body: `{"status":"duplicate"}`) |
| `webhook.duplicate_pr_sha` | 200 | Different `delivery_id`, same `(pr_number, head_sha)` already has RECEIVED run (success) |
| `internal_error` | 500 | Unexpected exception (no internal details leaked) |

No secrets, stack traces, or internal identifiers in error responses.

---

## 10. Configuration

### 10.1 Settings (`packages/config/settings.py`)

Using `pydantic-settings` with env vars from `.env.example`:

| Setting | Env Var | Type | Default |
|---|---|---|---|
| app_env | `APP_ENV` | str | "development" |
| log_level | `LOG_LEVEL` | str | "INFO" |
| github_app_id | `GITHUB_APP_ID` | int | required |
| github_private_key | `GITHUB_PRIVATE_KEY` | str | required |
| github_webhook_secret | `GITHUB_WEBHOOK_SECRET` | str | required |
| database_url | `DATABASE_URL` | str | required |
| redis_url | `REDIS_URL` | str | "redis://localhost:6379/0" |

### 10.2 Stream Names (constants in `packages/config/redis.py`)

```python
STREAM_HIGH = "meridian:reviews:high"
STREAM_MEDIUM = "meridian:reviews:medium"
STREAM_LOW = "meridian:reviews:low"
STREAM_DEADLETTER = "meridian:reviews:deadletter"
CONSUMER_GROUP = "meridian-workers"
```

---

## 11. Observability

### 11.1 Structured Logging (`packages/observability/logging.py`)

- `structlog` with JSON output in production, console output in development
- Every log entry includes: `timestamp`, `level`, `event`, `delivery_id` (when applicable), `trace_id`
- Redaction: repository content, diffs, prompts, key material → never logged
- `X-GitHub-Delivery` logged on every webhook touch for end-to-end delivery tracing

### 11.2 Tracing (`packages/observability/tracing.py`)

- OpenTelemetry tracer with spans for: `webhook.receive`, `webhook.verify`, `webhook.enqueue` (outbox publisher), `worker.consume`, `worker.process`
- **Cross-process trace context propagation (ADR-006):** The W3C `traceparent` is carried in the `JobMessage` schema (not in Redis Streams metadata). The outbox publisher injects the current span context via `opentelemetry.propagate.inject()` into the `traceparent` field before `XADD`. The worker extracts it via `opentelemetry.propagate.extract()` on the `JobMessage.traceparent` field and creates a child span. This preserves the parent-child span relationship across the API→worker process boundary.
- Trace attributes: `tenant_id`, `repository_id`, `review_run_id`, `stage`, `latency_ms`
- No raw source code or secrets in trace attributes (per `OBSERVABILITY.md §3`)

---

## 12. Test Plan

### 12.1 Unit Tests (`tests/unit/`)

| File | Tests |
|---|---|
| `test_hmac_verify.py` | Valid signature, invalid signature, missing header, wrong format, empty body |
| `test_jwt_generation.py` | Correct JWT structure, expiry, issuer, algorithm |
| `test_event_filter.py` | Allowed events pass, disallowed rejected, action filtering per event |
| `test_job_message.py` | Serialization/deserialization roundtrip, field validation, traceparent injection/extraction |
| `test_advisory_lock.py` | Lock key derivation (hashtextextended), concurrent lock conflict (mocked) |
| `test_audit_hash.py` | Hash chain: first entry, subsequent entries, tamper detection, sequence gap on rollback (mocked) |
| `test_error_envelope.py` | Each webhook error code maps to correct HTTP status + envelope shape |
| `test_token_cache.py` | L1 hit (no Redis call), L1 miss → L2 hit, L2 miss → GitHub fetch, invalidation clears both L1+L2 (mocked Redis) |

> **Note:** Model/schema tests that require PostgreSQL (pgvector, JSONB, advisory locks, BIGSERIAL) are **integration tests**, not unit tests — per `CODE_STANDARDS.md §6`, unit tests have "no I/O, no network." Pure unit tests mock the DB/session layer.

### 12.2 Integration Tests (`tests/integration/`)

| File | Tests |
|---|---|
| `test_models.py` | Model creation, FK relationships, unique constraints (real PostgreSQL via docker-compose) |
| `test_webhook_ingestion.py` | Post fake webhook → verify DB outbox row (enqueued=false), no Redis write yet |
| `test_outbox_publisher.py` | Insert outbox row → run publisher → verify XADD to Redis + enqueued=true |
| `test_worker_consumption.py` | Enqueue a job → run worker → verify review_run created in RECEIVED |
| `test_idempotency.py` | Post same delivery_id twice → only one DB row; post different delivery_id same (pr,sha) → no duplicate review_run |
| `test_priority_streams.py` | Enqueue to high/medium/low → verify consumption order |
| `test_janitor.py` | Stall a message → XAUTOCLAIM re-delivers → dead-letter after 3 attempts |
| `test_audit_sequence.py` | Concurrent inserts → no duplicate sequence_number; hash chain intact |

### 12.3 E2E Test (`tests/e2e/`)

| File | Tests |
|---|---|
| `test_webhook_to_review_run.py` | Mock GitHub webhook → FastAPI → Redis → Worker → verify review_run in RECEIVED in DB |

### 12.4 Test Infrastructure

- Integration tests require `docker compose up -d postgres redis` (marked `@pytest.mark.integration`)
- Unit tests have no external dependencies (marked `@pytest.mark.unit`)
- E2E tests use FastAPI `TestClient` + real Redis + real Postgres (marked `@pytest.mark.e2e`)
- Fake webhook payloads stored in `tests/fixtures/webhooks/`

---

## 13. ADRs

| ADR | Title | Decision |
|---|---|---|
| [ADR-006](../adr/adr-006-phase1-github-app-webhook-ingestion.md) | Phase 1 — GitHub App + webhook ingestion layer | Single consolidated ADR covering: webhook ingestion architecture (verify → outbox → ack within 10s; idempotency via delivery_id + advisory lock + second check on (pull_request_id, head_sha); thin route → service function with explicit transaction); transactional outbox pattern (webhook_deliveries doubles as outbox; publisher coroutine in worker polls SKIP LOCKED, XADD, marks enqueued; decouples Redis from 10s critical path); Redis Streams priority lanes (separate high/medium/low streams); database schema design (14 tables upfront; BIGSERIAL PKs; pgvector; audit sequence via PostgreSQL SEQUENCE); GitHub adapter pattern (JWT from App private key; L1 in-memory + L2 Redis shared token cache; rate-limit-aware httpx client); worker consumer design (XREADGROUP at-least-once; XAUTOCLAIM janitor; dead-letter after 3 attempts; XACK after DB commit); Stripe-style error envelope (type, code, param, request_id, doc_url; webhook error code taxonomy; updates CODE_STANDARDS.md §3); trace context propagation (W3C traceparent in JobMessage; OTel inject/extract across Redis Streams process boundary) |

---

## 14. Build Order

| Step | Component | Description |
|---|---|---|
| 1 | `packages/config/` | Settings, DB engine, Redis client — foundation everything depends on |
| 2 | `packages/models/` | All 14 tables (SQLAlchemy 2.0, including outbox columns on webhook_deliveries) + Pydantic schemas + enums |
| 3 | `db/migrations/` | Alembic setup + initial migration creating all tables + pgvector extension + audit_events_seq |
| 4 | `packages/observability/` | structlog + OTel setup (incl. traceparent inject/extract helpers) |
| 5 | `packages/security/` | HMAC verification + advisory lock helpers (hashtextextended key derivation) |
| 6 | `packages/github/` | JWT, two-layer (L1/L2) installation token cache, webhook verification, API client |
| 7 | `packages/orchestration/` | ingestion.py service function + Redis Streams producer + consumer + stream config + JobMessage (with traceparent) |
| 8 | `apps/api/` | FastAPI app, lifespan, routers (thin handlers → service), deps, error envelope |
| 9 | `apps/worker/` | Consumer loop, outbox_publisher, janitor, graceful shutdown |
| 10 | `tests/` | Unit + integration + e2e |
| 11 | ADRs | ADR-006 (consolidated Phase 1 ADR) |
| 12 | `CODE_STANDARDS.md §3` | Update error envelope to Stripe-style (ADR-006) |
| 13 | `track.md` + commit | Update track, commit all |

Each step produces a testable, committable unit. Steps 1-7 are packages (no running process). Steps 8-9 are apps (runnable). Step 10 validates everything.

---

## 15. Key Design Decisions Summary

| Decision | Rationale |
|---|---|
| Raw body via `Request.body()` for HMAC + JSON | Avoids re-reading stream; FastAPI route takes `request: Request` not a Pydantic model |
| Transactional outbox pattern (ADR-006) | Eliminates dual-write hazard between DB commit and Redis XADD; decouples Redis availability from the 10-second webhook critical path |
| `webhook_deliveries` doubles as outbox table | Avoids a separate outbox table; `enqueued`/`enqueued_at` columns track XADD status |
| Outbox publisher in worker process (SKIP LOCKED) | Partitions work across worker instances; API scaling doesn't multiply publishers; ingestion fully decoupled from Redis |
| Route handler delegates to `ingest_webhook()` service | Thin handlers per `CODE_STANDARDS.md`; explicit `async with session.begin()` transaction scope — no reliance on FastAPI dependency teardown for lock release |
| Advisory lock on `hashtextextended(repo:pr:sha)` | Prevents race condition on concurrent redelivery; 64-bit key, collisions astronomically rare |
| Second idempotency check on `(pull_request_id, head_sha)` | Prevents duplicate review_runs when GitHub redelivers with a new delivery_id but same payload |
| Job message = reference + `traceparent`, not full payload | Keeps Redis stream entries small; worker reads payload from DB; traceparent preserves OTel parent-child span across process boundary |
| Separate priority streams vs single stream | True priority semantics; consumer reads high→medium→low |
| XACK after DB commit | At-least-once delivery — crash before ack means redelivery, idempotency prevents dupes |
| All 13 tables upfront | Avoid migration churn later; empty tables are cheap; FK relationships are correct from day 1 |
| Two-layer (L1 in-memory + L2 Redis) token cache | L1 avoids Redis round-trips for hot tokens; L2 shares tokens across all processes; invalidation propagates via Redis DEL |
| Stripe-style error envelope (type, code, param, request_id, doc_url) | Machine-readable taxonomy; codified webhook error codes prevent ad-hoc strings; dual-level type+code matches industry standard |
| Audit sequence via PostgreSQL SEQUENCE | Atomic, non-blocking under concurrent inserts; gaps on rollback are acceptable (hash-chain integrity is from linking, not contiguity) |
| App factory pattern | Testable; no global state; settings injected |
| `webhook_deliveries` table (14th table) | Required for idempotency + outbox; not in original 13 but is an implementation detail of ingestion |

---

## 16. Out of Scope — Documented as Remaining

1. **GitHub OAuth App** — dashboard sign-in (identity/session). Deferred; Phase 1+ when dashboard is built.
2. **Review publishing** — posting comments/reviews back to GitHub PRs. Deferred to Phase 3 when agents exist; the `GitHubClient.post_review()` method is defined but not called.
3. **LangGraph orchestrator** — review state machine transitions (RECEIVED→...→COMPLETED). Deferred to Phase 3.
4. **Risk engine** — risk tier determination. Phase 1 defaults all jobs to MEDIUM.
5. **Repository indexing** — Tree-sitter, SCIP/LSP, embeddings. Phase 2.
6. **BYOK/KMS** — envelope encryption of user API keys. Phase 5. The `api_keys.encrypted_key` column exists but stores plaintext in Phase 1 (dev only).
7. **Sandbox execution** — Phase 4.
8. **Next.js dashboard** — Phase 5+.

These items are tracked in `track.md` and will be picked up in their respective phases.
