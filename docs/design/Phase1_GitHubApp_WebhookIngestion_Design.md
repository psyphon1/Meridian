# Meridian — Phase 1 Design Spec
# GitHub App + Webhook Ingestion Layer

---
Created: 2026-09-13
Author: Chinmay Duse (psyphon1)
Version: 1.0.0
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
├── producer.py            # XADD to priority streams
├── consumer.py            # XREADGROUP, consumer group management
├── streams.py             # Stream name constants, dead-letter, XTRIM config
└── messages.py            # JobMessage Pydantic schema (serialized as JSON in stream)
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

### 4.1 Step-by-Step

```
POST /v1/webhooks/github arrives
  │
  ├─ 1. Read raw body + headers (do NOT parse JSON yet)
  ├─ 2. Extract: X-Hub-Signature-256, X-GitHub-Event, X-GitHub-Delivery
  ├─ 3. Verify HMAC-SHA256(raw_body, webhook_secret) — timing-safe compare
  │     └─ FAIL → return 401 (log: signature_verify_failed, delivery_id)
  ├─ 4. Event/action filter:
  │     ├─ X-GitHub-Event in {pull_request, installation, installation_repositories}?
  │     └─ Action in allowed set for that event?
  │     └─ NO → return 200 + "ignored" (fast reject, no DB write)
  ├─ 5. Parse JSON body → typed Pydantic model (per event type)
  ├─ 6. Open DB transaction:
  │     ├─ a. pg_advisory_xact_lock(hash(repository_id + pr_number + head_sha))
  │     ├─ b. Check webhook_deliveries for X-GitHub-Delivery — if exists → 200 (idempotent)
  │     ├─ c. Insert webhook_delivery (delivery_id, event, action, payload_ref)
  │     ├─ d. Determine priority tier (default: MEDIUM for Phase 1)
  │     ├─ e. XADD job to meridian:reviews:{priority} stream
  │     ├─ f. Commit transaction (releases advisory lock)
  │     └─ g. Return 200
  └─ Error: any exception → 500, structured log, transaction rollback (no partial state)
```

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
  "enqueued_at": "2026-09-13T12:00:00Z"
}
```

The job message is a **reference**, not the full payload. The worker reads the full payload from the `webhook_deliveries` table by `delivery_id`. This keeps stream entries small and avoids duplicating large diffs in Redis.

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

#### `webhook_deliveries` (idempotency table — not in original 13)
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| delivery_id | VARCHAR(255) | UNIQUE, NOT NULL (X-GitHub-Delivery) |
| event | VARCHAR(50) | NOT NULL |
| action | VARCHAR(50) | NOT NULL |
| payload | JSONB | NOT NULL (full webhook payload) |
| processed | BOOLEAN | DEFAULT false |
| processed_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |

### 5.2 Indexes

| Table | Index |
|---|---|
| pull_requests | UNIQUE(repository_id, github_pr_number) |
| repositories | UNIQUE(github_repo_id) |
| installations | UNIQUE(github_installation_id) |
| webhook_deliveries | UNIQUE(delivery_id) |
| review_runs | INDEX(pull_request_id), INDEX(status) |
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
    """In-memory cache of installation access tokens, keyed by installation_id."""
    
    async def get_token(self, installation_id: int) -> str:
        # Return cached token if not near expiry
        # Otherwise call POST /app/installations/{id}/access_tokens
    
    async def invalidate(self, installation_id: int) -> None:
        # Called on 401 response
```

- Token TTL = expiry timestamp - 60s safety margin
- On 401 from any GitHub API call: invalidate cache, regenerate token, retry once
- Cache is per-process (in-memory); acceptable for Phase 1

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
    """XADD a job message to the appropriate priority stream. Returns stream ID."""
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

### 7.6 At-Least-Once Semantics

- A message is only `XACK`'d **after** the DB transaction commits
- If the worker crashes before `XACK`: the message remains in the PEL
- On restart or janitor sweep: `XAUTOCLAIM` re-delivers the message
- The consumer is idempotent: `webhook_deliveries.delivery_id` unique constraint prevents duplicates
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
  ├─ Start janitor coroutine
  ├─ Register signal handlers (SIGTERM → graceful drain)
  └─ Main loop (XREADGROUP BLOCK 5000):
       ├─ Read from meridian:reviews:high (if messages)
       ├─ Read from meridian:reviews:medium (if high empty)
       ├─ Read from meridian:reviews:low (if medium empty)
       ├─ For each message:
       │    ├─ Parse JobMessage from stream fields
       │    ├─ Fetch full webhook payload from webhook_deliveries by delivery_id
       │    ├─ DB transaction:
       │    │    ├─ Upsert installation (from payload)
       │    │    ├─ Upsert repository (from payload)
       │    │    ├─ Upsert pull_request (from payload)
       │    │    ├─ Create review_run (status=RECEIVED, risk_tier=MEDIUM)
       │    │    ├─ Insert audit_event (hash-chained)
       │    │    ├─ Mark webhook_delivery.processed = true
       │    │    └─ Commit
       │    ├─ XACK the message (after commit = at-least-once)
       │    └─ Log: job_processed {delivery_id, run_id, stream, duration_ms}
       └─ On SIGTERM: stop reading, finish current message, XACK, drain, exit 0
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

All API errors follow the consistent envelope from `CODE_STANDARDS.md §3`:
```json
{"error": {"code": "...", "message": "...", "details": {...}}}
```

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

- OpenTelemetry tracer with spans for: `webhook.receive`, `webhook.verify`, `webhook.enqueue`, `worker.consume`, `worker.process`
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
| `test_job_message.py` | Serialization/deserialization roundtrip, field validation |
| `test_advisory_lock.py` | Lock acquisition, concurrent lock conflict (mocked) |
| `test_models.py` | Model creation, FK relationships, unique constraints (in-memory SQLite) |
| `test_audit_hash.py` | Hash chain: first entry, subsequent entries, tamper detection |

### 12.2 Integration Tests (`tests/integration/`)

| File | Tests |
|---|---|
| `test_webhook_ingestion.py` | Post fake webhook → verify DB row + Redis stream entry |
| `test_worker_consumption.py` | Enqueue a job → run worker → verify review_run created in RECEIVED |
| `test_idempotency.py` | Post same webhook twice → only one DB row + one stream entry |
| `test_priority_streams.py` | Enqueue to high/medium/low → verify consumption order |
| `test_janitor.py` | Stall a message → XAUTOCLAIM re-delivers → dead-letter after 3 attempts |

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
| ADR-006 | Webhook ingestion architecture | Verify → enqueue → ack within 10s; idempotency via delivery_id unique constraint + advisory lock |
| ADR-007 | Redis Streams priority lanes | Separate streams per priority tier (high/medium/low) with consumer reading high→medium→low |
| ADR-008 | Database schema design | All 13 core tables + webhook_deliveries created upfront; BIGSERIAL PKs; pgvector extension |
| ADR-009 | GitHub adapter pattern | JWT from App private key, installation token cache per-process, rate-limit-aware httpx client |
| ADR-010 | Worker consumer design | XREADGROUP with at-least-once, XAUTOCLAIM janitor, dead-letter after 3 attempts, XACK after DB commit |

---

## 14. Build Order

| Step | Component | Description |
|---|---|---|
| 1 | `packages/config/` | Settings, DB engine, Redis client — foundation everything depends on |
| 2 | `packages/models/` | All 14 tables (SQLAlchemy 2.0) + Pydantic schemas + enums |
| 3 | `db/migrations/` | Alembic setup + initial migration creating all tables + pgvector extension |
| 4 | `packages/observability/` | structlog + OTel setup |
| 5 | `packages/security/` | HMAC verification + advisory lock helpers |
| 6 | `packages/github/` | JWT, installation tokens, webhook verification, API client |
| 7 | `packages/orchestration/` | Redis Streams producer + consumer + stream config |
| 8 | `apps/api/` | FastAPI app, lifespan, routers, deps |
| 9 | `apps/worker/` | Consumer loop, janitor, graceful shutdown |
| 10 | `tests/` | Unit + integration + e2e |
| 11 | ADRs | ADR-006 through ADR-010 |
| 12 | `track.md` + commit | Update track, commit all |

Each step produces a testable, committable unit. Steps 1-7 are packages (no running process). Steps 8-9 are apps (runnable). Step 10 validates everything.

---

## 15. Key Design Decisions Summary

| Decision | Rationale |
|---|---|
| Raw body read once for HMAC + JSON | Avoids re-reading stream; FastAPI body is consumed once |
| Advisory lock on hash(repo+pr+sha) | Prevents race condition on concurrent redelivery without blocking unrelated webhooks |
| Job message = reference, not full payload | Keeps Redis stream entries small; worker reads payload from DB |
| Separate priority streams vs single stream | True priority semantics; consumer reads high→medium→low |
| XACK after DB commit | At-least-once delivery — crash before ack means redelivery, idempotency prevents dupes |
| All 13 tables upfront | Avoid migration churn later; empty tables are cheap; FK relationships are correct from day 1 |
| In-memory token cache (per-process) | Simple for Phase 1; Redis-based distributed cache can be added when horizontal scaling matters |
| App factory pattern | Testable; no global state; settings injected |
| webhook_deliveries table (14th table) | Required for idempotency; not in original 13 but is an implementation detail of ingestion |

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
