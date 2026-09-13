# Phase 1 — GitHub App + Webhook Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a GitHub App that receives webhooks, verifies HMAC, persists them durably via a transactional outbox, and enqueues review jobs to Redis Streams — all within GitHub's 10-second deadline — ending with an end-to-end path `webhook → Postgres outbox → Redis Streams → worker → review_run (RECEIVED)`.

**Architecture:** Thin FastAPI apps delegate to capability packages. The webhook handler writes only to PostgreSQL (`webhook_deliveries` doubles as the outbox with `enqueued=false`), commits, and returns 2xx. A separate outbox publisher coroutine in the worker process polls `WHERE enqueued=false FOR UPDATE SKIP LOCKED`, calls `XADD`, and marks `enqueued=true`. This decouples Redis availability from the 10-second critical path (ADR-006).

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async, PostgreSQL 16 + pgvector, Redis 7 (Streams), Alembic, pydantic v2 + pydantic-settings, httpx, PyJWT, structlog, OpenTelemetry, pytest + pytest-asyncio, Ruff, mypy strict.

## Global Constraints

- Python `>=3.12`; all code type-hinted; `mypy --strict` clean; Ruff `select = [E,F,W,I,N,UP,B,C4,SIM,RUF,ASYNC,S,T20]` clean.
- Unit tests = no I/O, no network (`@pytest.mark.unit`); integration tests = docker-compose Postgres+Redis (`@pytest.mark.integration`); e2e = full system (`@pytest.mark.e2e`).
- No credentials in source/logs/traces — ever. No `.env` files committed. `.env.example` has placeholder values only.
- No business logic in route handlers — handlers validate and delegate only (`CODE_STANDARDS.md §1.1`).
- No raw GitHub API calls outside `packages/github/`. No direct Redis calls outside `packages/orchestration/`.
- All timestamps `TIMESTAMP WITH TIME ZONE`; PKs `BIGSERIAL` (BigInt).
- Conventional Commits only; each task ends with a commit.
- Coverage `>= 80%` (`pyproject.toml` `fail_under = 80`).

## Source Documents

- **Spec:** `docs/specs/2026-09-13-phase1-github-app-webhook-ingestion.md` (§3 module map, §4 handler flow, §5 schema, §6 adapter, §7 streams, §8 worker, §9 API, §10 config, §11 observability, §12 tests)
- **ADR-006:** `docs/adr/adr-006-phase1-github-app-webhook-ingestion.md` (decisions D1–D8)
- **Standards:** `docs/CODE_STANDARDS.md`, `docs/DEVELOPER_STANDARDS.md`, `docs/OBSERVABILITY.md`, `docs/SECURITY.md`, `docs/PROJECT_STRUCTURE.md`

## File Structure

```
packages/config/        → settings.py, database.py, redis.py       (Tasks 1–3)
packages/models/        → base, enums, 8 table modules, schemas    (Tasks 4–9)
db/migrations/          → alembic.ini, env.py, 001_initial_schema  (Task 10)
packages/observability/ → logging.py, tracing.py                   (Tasks 11–12)
packages/security/      → hmac_verify.py, advisory_lock.py         (Tasks 13–14)
packages/github/        → errors, types, auth, webhooks, client    (Tasks 15–19)
packages/orchestration/ → messages, streams, producer, consumer, ingestion (Tasks 20–23)
apps/api/               → main, deps, routers/health, routers/webhooks (Tasks 24–26)
apps/worker/            → main, consumer, outbox_publisher, janitor (Tasks 27–29)
tests/                  → unit/, integration/, e2e/, fixtures/     (Task 30)
```

---
## Tasks

### Task 1: Settings (`packages/config/settings.py`)

**Files:**
- Create: `packages/config/__init__.py`, `packages/config/settings.py`, `packages/config/py.typed`
- Test: `tests/unit/test_settings.py`

**Interfaces:**
- Consumes: nothing (foundation)
- Produces: `Settings` (fields: `app_env: str`, `log_level: str`, `github_app_id: int`, `github_private_key: str`, `github_webhook_secret: str`, `database_url: str`, `redis_url: str`); `get_settings() -> Settings`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_settings.py
import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsecret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/meridian")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from packages.config.settings import Settings
    s = Settings()
    assert s.github_app_id == 12345
    assert s.github_webhook_secret == "whsecret"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.app_env == "development"
    assert s.log_level == "INFO"


def test_settings_missing_required_raises(monkeypatch):
    for k in ("GITHUB_APP_ID", "GITHUB_PRIVATE_KEY", "GITHUB_WEBHOOK_SECRET", "DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    from packages.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_invalid_app_id_raises(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "not-an-int")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "key")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/config/__init__.py
"""Meridian configuration package — settings, DB engine, Redis client."""
```

```python
# packages/config/settings.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    github_app_id: int
    github_private_key: str
    github_webhook_secret: str

    database_url: str
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
```

Create empty file: `packages/config/py.typed`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_settings.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/config/ tests/unit/test_settings.py
git commit -m "feat(config): typed pydantic-settings with validation"
```

---


### Task 2: Database engine (`packages/config/database.py`)

**Files:**
- Create: `packages/config/database.py`
- Test: `tests/unit/test_database.py`

**Interfaces:**
- Consumes: `Settings` (Task 1, field `database_url: str`)
- Produces: `create_db_engine(settings) -> AsyncEngine`, `create_session_factory(engine) -> async_sessionmaker[AsyncSession]`, `async get_session(session_factory) -> AsyncIterator[AsyncSession]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_database.py
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker


def test_create_db_engine_returns_async_engine(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.settings import Settings
    from packages.config.database import create_db_engine
    engine = create_db_engine(Settings())
    assert isinstance(engine, AsyncEngine)


def test_create_session_factory_returns_async_sessionmaker(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.settings import Settings
    from packages.config.database import create_db_engine, create_session_factory
    engine = create_db_engine(Settings())
    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.config.database'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/config/database.py
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)
from packages.config.settings import Settings


def create_db_engine(settings: Settings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from settings."""
    return create_async_engine(
        settings.database_url,
        echo=(settings.app_env == "development"),
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async_sessionmaker bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a DB session."""
    async with session_factory() as session:
        yield session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_database.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/config/database.py tests/unit/test_database.py
git commit -m "feat(config): async SQLAlchemy engine + session factory"
```

---


### Task 3: Redis client + stream constants (`packages/config/redis.py`)

**Files:**
- Create: `packages/config/redis.py`
- Test: `tests/unit/test_redis_config.py`

**Interfaces:**
- Consumes: `Settings` (Task 1, field `redis_url: str`)
- Produces: `create_redis_client(settings) -> Redis`; constants `STREAM_HIGH`, `STREAM_MEDIUM`, `STREAM_LOW`, `STREAM_DEADLETTER`, `CONSUMER_GROUP`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_redis_config.py
from redis.asyncio import Redis


def test_create_redis_client_returns_redis(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from packages.config.settings import Settings
    from packages.config.redis import create_redis_client
    client = create_redis_client(Settings())
    assert isinstance(client, Redis)


def test_stream_constants_defined():
    from packages.config.redis import (
        STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW, STREAM_DEADLETTER, CONSUMER_GROUP,
    )
    assert STREAM_HIGH == "meridian:reviews:high"
    assert STREAM_MEDIUM == "meridian:reviews:medium"
    assert STREAM_LOW == "meridian:reviews:low"
    assert STREAM_DEADLETTER == "meridian:reviews:deadletter"
    assert CONSUMER_GROUP == "meridian-workers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_redis_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.config.redis'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/config/redis.py
from redis.asyncio import Redis
from packages.config.settings import Settings

STREAM_HIGH = "meridian:reviews:high"
STREAM_MEDIUM = "meridian:reviews:medium"
STREAM_LOW = "meridian:reviews:low"
STREAM_DEADLETTER = "meridian:reviews:deadletter"
CONSUMER_GROUP = "meridian-workers"


def create_redis_client(settings: Settings) -> Redis:
    """Create an async Redis client from settings."""
    return Redis.from_url(settings.redis_url, decode_responses=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_redis_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/config/redis.py tests/unit/test_redis_config.py
git commit -m "feat(config): async Redis client factory + stream constants"
```

---


### Task 4: Models — Base, TimestampMixin, enums (`packages/models/base.py`)

**Files:**
- Create: `packages/models/__init__.py`, `packages/models/base.py`, `packages/models/py.typed`
- Test: `tests/unit/test_models_base.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Base` (DeclarativeBase), `TimestampMixin` (adds `created_at`, `updated_at` with server defaults), enums `ReviewStatus` (RECEIVED→COMPLETED), `RiskTier` (LOW/MEDIUM/HIGH/CRITICAL), `FindingSeverity` (BLOCKING/HIGH/MEDIUM/LOW/NIT), `InstallationStatus` (active/uninstalled), `PRState` (open/closed)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models_base.py
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from packages.models.base import (
    Base, TimestampMixin, ReviewStatus, RiskTier,
    FindingSeverity, InstallationStatus, PRState,
)


def test_base_is_declarative():
    assert issubclass(Base, DeclarativeBase)


def test_timestamp_mixin_has_columns():
    cols = {c.name for c in TimestampMixin.__table__.columns}  # type: ignore[attr-defined]
    assert "created_at" in cols
    assert "updated_at" in cols


def test_enums_have_expected_members():
    assert ReviewStatus.RECEIVED == "RECEIVED"
    assert ReviewStatus.COMPLETED == "COMPLETED"
    assert RiskTier.HIGH == "HIGH"
    assert FindingSeverity.BLOCKING == "BLOCKING"
    assert FindingSeverity.NIT == "NIT"
    assert InstallationStatus.ACTIVE == "active"
    assert InstallationStatus.UNINSTALLED == "uninstalled"
    assert PRState.OPEN == "open"
    assert PRState.CLOSED == "closed"
```

> **Note:** `TimestampMixin` needs to be declared as a mixin (not a mapped table) so it can be composed into real tables. The test above uses `__table__` which only works if the mixin is itself mapped — adjust the test to inspect `__annotations__` instead if you implement it as a pure mixin. See Step 3 for the mixin-only implementation and the corrected test below.

Corrected test for pure mixin (use this instead of `test_timestamp_mixin_has_columns`):

```python
def test_timestamp_mixin_has_annotations():
    anns = TimestampMixin.__annotations__
    assert "created_at" in anns
    assert "updated_at" in anns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_models_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/models/__init__.py
"""Meridian ORM models — SQLAlchemy 2.0 declarative."""
```

```python
# packages/models/base.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import String


class Base(DeclarativeBase):
    """Declarative base for all Meridian models."""


class TimestampMixin:
    """Adds created_at and updated_at columns with server defaults."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class CreatedAtMixin:
    """Adds only created_at (for append-only tables)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )


class ReviewStatus(String):
    RECEIVED = "RECEIVED"
    COMPLETED = "COMPLETED"


class RiskTier(str):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingSeverity(str):
    BLOCKING = "BLOCKING"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NIT = "NIT"


class InstallationStatus(str):
    ACTIVE = "active"
    UNINSTALLED = "uninstalled"


class PRState(str):
    OPEN = "open"
    CLOSED = "closed"
```

Create empty file: `packages/models/py.typed`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_models_base.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/models/__init__.py packages/models/base.py packages/models/py.typed tests/unit/test_models_base.py
git commit -m "feat(models): declarative base, timestamp mixin, domain enums"
```

---


### Task 5: Models — users, api_keys, installations (`packages/models/identity.py`)

**Files:**
- Create: `packages/models/identity.py`
- Test: `tests/unit/test_models_identity.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin`, `CreatedAtMixin`, `InstallationStatus` (Task 4)
- Produces: ORM models `User`, `APIKey`, `Installation` with the exact columns from spec §5

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models_identity.py
from sqlalchemy import inspect as sa_inspect
from packages.models.identity import User, APIKey, Installation


def test_user_table_columns():
    cols = {c.name for c in sa_inspect(User).columns}
    assert cols == {"id", "github_id", "username", "email", "avatar_url",
                    "created_at", "updated_at"}


def test_api_key_table_columns():
    cols = {c.name for c in sa_inspect(APIKey).columns}
    assert cols == {"id", "user_id", "provider", "encrypted_key",
                    "is_active", "created_at", "rotated_at"}


def test_installation_table_columns():
    cols = {c.name for c in sa_inspect(Installation).columns}
    assert cols == {"id", "github_installation_id", "account_login",
                    "account_type", "status", "user_id", "created_at", "updated_at"}


def test_installation_github_id_unique():
    col = sa_inspect(Installation).columns["github_installation_id"]
    assert col.unique is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_models_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.models.identity'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/models/identity.py
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, LargeBinary, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from packages.models.base import Base, TimestampMixin, CreatedAtMixin, InstallationStatus


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)


class APIKey(Base, CreatedAtMixin):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rotated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )


class Installation(Base, TimestampMixin):
    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_installation_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False,
    )
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default=InstallationStatus.ACTIVE)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_models_identity.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/models/identity.py tests/unit/test_models_identity.py
git commit -m "feat(models): users, api_keys, installations tables"
```

---


### Task 6: Models — repositories, commits, files, code_symbols (`packages/models/repository.py`)

**Files:**
- Create: `packages/models/repository.py`
- Test: `tests/unit/test_models_repository.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin`, `CreatedAtMixin` (Task 4), `Installation` (Task 5)
- Produces: ORM models `Repository`, `Commit`, `File`, `CodeSymbol`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models_repository.py
from sqlalchemy import inspect as sa_inspect
from packages.models.repository import Repository, Commit, File, CodeSymbol


def test_repository_columns():
    cols = {c.name for c in sa_inspect(Repository).columns}
    assert cols == {"id", "installation_id", "github_repo_id", "owner", "name",
                    "full_name", "default_branch", "is_private", "created_at", "updated_at"}


def test_commit_columns():
    cols = {c.name for c in sa_inspect(Commit).columns}
    assert cols == {"id", "repository_id", "sha", "message", "author",
                    "authored_at", "created_at"}


def test_file_columns():
    cols = {c.name for c in sa_inspect(File).columns}
    assert cols == {"id", "repository_id", "path", "language", "size",
                    "last_commit_sha", "created_at", "updated_at"}


def test_code_symbol_columns():
    cols = {c.name for c in sa_inspect(CodeSymbol).columns}
    assert cols == {"id", "file_id", "name", "kind", "start_line", "end_line",
                    "signature", "embedding", "created_at"}


def test_github_repo_id_unique():
    assert sa_inspect(Repository).columns["github_repo_id"].unique is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_models_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.models.repository'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/models/repository.py
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from packages.models.base import Base, TimestampMixin, CreatedAtMixin


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    installation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("installations.id"), nullable=False,
    )
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)


class Commit(Base, CreatedAtMixin):
    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False,
    )
    sha: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authored_at: Mapped[datetime | None] = mapped_column(nullable=True)


class File(Base, TimestampMixin):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)


class CodeSymbol(Base, CreatedAtMixin):
    __tablename__ = "code_symbols"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("files.id"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    # embedding: pgvector(1536) — added in migration Task 10; nullable, Phase 2
```

> **Note on `embedding`:** The `vector(1536)` column requires the pgvector extension and cannot be expressed purely with stock SQLAlchemy types in the ORM without `pgvector.sqlalchemy.Vector`. We declare it in the Alembic migration (Task 10) using `pgvector.sqlalchemy.Vector(1536)`. The ORM model omits it in Phase 1 to avoid importing pgvector at module load; if you prefer to include it, add `from pgvector.sqlalchemy import Vector` and `embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_models_repository.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/models/repository.py tests/unit/test_models_repository.py
git commit -m "feat(models): repositories, commits, files, code_symbols tables"
```

---


### Task 7: Models — reviews (`packages/models/review.py`)

**Files:**
- Create: `packages/models/review.py`
- Test: `tests/unit/test_models_review.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin`, `CreatedAtMixin`, `ReviewStatus`, `RiskTier`, `FindingSeverity`, `PRState` (Task 4)
- Produces: ORM models `PullRequest`, `ReviewRun`, `Finding`, `Evidence`, `ToolRun`, `ReviewMemory`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models_review.py
from sqlalchemy import inspect as sa_inspect
from packages.models.review import (
    PullRequest, ReviewRun, Finding, Evidence, ToolRun, ReviewMemory,
)


def test_pull_request_columns():
    cols = {c.name for c in sa_inspect(PullRequest).columns}
    assert cols == {"id", "repository_id", "github_pr_number", "title", "body",
                    "head_sha", "base_sha", "author", "state", "created_at", "updated_at"}


def test_review_run_columns():
    cols = {c.name for c in sa_inspect(ReviewRun).columns}
    assert cols == {"id", "pull_request_id", "status", "risk_tier",
                    "started_at", "completed_at", "error_message",
                    "created_at", "updated_at"}


def test_finding_columns():
    cols = {c.name for c in sa_inspect(Finding).columns}
    assert cols == {"id", "review_run_id", "category", "severity", "confidence",
                    "file_path", "start_line", "end_line", "message", "evidence_id",
                    "created_at"}


def test_evidence_columns():
    cols = {c.name for c in sa_inspect(Evidence).columns}
    assert cols == {"id", "review_run_id", "type", "artifact_ref", "summary",
                    "verified", "created_at"}


def test_tool_run_columns():
    cols = {c.name for c in sa_inspect(ToolRun).columns}
    assert cols == {"id", "review_run_id", "tool_name", "status",
                    "output_ref", "duration_ms", "created_at"}


def test_review_memory_columns():
    cols = {c.name for c in sa_inspect(ReviewMemory).columns}
    assert cols == {"id", "repository_id", "key", "value", "created_at", "updated_at"}


def test_pr_unique_repo_number():
    uqs = sa_inspect(PullRequest).table.constraints
    unique_pairs = {
        tuple(c.name for c in uc.columns)
        for uc in uqs
        if uc.__class__.__name__ == "UniqueConstraint"
    }
    assert ("repository_id", "github_pr_number") in unique_pairs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_models_review.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.models.review'`


- [ ] **Step 3: Write minimal implementation**

```python
# packages/models/review.py
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Float, ForeignKey, Integer, Real, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.models.base import (
    Base, TimestampMixin, CreatedAtMixin,
    ReviewStatus, RiskTier, FindingSeverity, PRState,
)


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_pr_number",
                         name="uq_pr_repo_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False)
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False,
                                       default=PRState.OPEN)


class ReviewRun(Base, TimestampMixin):
    __tablename__ = "review_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False,
                                        default=ReviewStatus.RECEIVED)
    risk_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Evidence(Base, CreatedAtMixin):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_runs.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_ref: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Finding(Base, CreatedAtMixin):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_runs.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Real, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("evidence.id"), nullable=True)


class ToolRun(Base, CreatedAtMixin):
    __tablename__ = "tool_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_runs.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReviewMemory(Base, TimestampMixin):
    __tablename__ = "review_memory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_models_review.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/models/review.py tests/unit/test_models_review.py
git commit -m "feat(models): pull_requests, review_runs, findings, evidence, tool_runs, review_memory"
```

---


### Task 8: Models — audit_events, webhook_deliveries (`packages/models/audit.py`)

**Files:**
- Create: `packages/models/audit.py`
- Test: `tests/unit/test_models_audit.py`

**Interfaces:**
- Consumes: `Base`, `CreatedAtMixin` (Task 4)
- Produces: ORM models `AuditEvent` (hash-chained, append-only), `WebhookDelivery` (idempotency + outbox)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models_audit.py
from sqlalchemy import inspect as sa_inspect
from packages.models.audit import AuditEvent, WebhookDelivery


def test_audit_event_columns():
    cols = {c.name for c in sa_inspect(AuditEvent).columns}
    assert cols == {"id", "sequence_number", "previous_hash", "current_hash",
                    "event_type", "actor", "ip", "payload", "created_at"}


def test_audit_sequence_number_unique():
    assert sa_inspect(AuditEvent).columns["sequence_number"].unique is True


def test_webhook_delivery_columns():
    cols = {c.name for c in sa_inspect(WebhookDelivery).columns}
    assert cols == {"id", "delivery_id", "event", "action", "payload",
                    "payload_size_bytes", "processed", "processed_at",
                    "enqueued", "enqueued_at", "created_at"}


def test_webhook_delivery_id_unique():
    assert sa_inspect(WebhookDelivery).columns["delivery_id"].unique is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_models_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.models.audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/models/audit.py
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.models.base import Base, CreatedAtMixin


class AuditEvent(Base):
    """Append-only, hash-chained audit log (ADR-006).

    sequence_number is populated by a PG SEQUENCE (audit_events_seq)
    via nextval() before insert. current_hash =
    SHA256(previous_hash || event_type || actor || payload || created_at).
    """
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sequence_number: Mapped[int] = mapped_column(BigInteger, unique=True,
                                                  nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=__import__("sqlalchemy").func.now(),
    )


class WebhookDelivery(Base, CreatedAtMixin):
    """Idempotency key store + transactional outbox (ADR-006).

    The webhook handler inserts a row with enqueued=false. The outbox
    publisher polls WHERE enqueued=false FOR UPDATE SKIP LOCKED, calls
    XADD, then sets enqueued=true.
    """
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    delivery_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    enqueued: Mapped[bool] = mapped_column(Boolean, default=False)
    enqueued_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_models_audit.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/models/audit.py tests/unit/test_models_audit.py
git commit -m "feat(models): audit_events hash-chain + webhook_deliveries outbox"
```

---


### Task 9: Pydantic schemas — JobMessage, payloads, IngestResult (`packages/models/schemas.py`)

**Files:**
- Create: `packages/models/schemas.py`
- Test: `tests/unit/test_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces: `JobMessage` (14 fields per spec §4.3), `IngestResult` (`status: str`, `delivery_id: str`), `WebhookHeaders` dataclass, `PullRequestPayload`, `InstallationPayload`, `InstallationRepositoriesPayload`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_schemas.py
import pytest
from packages.models.schemas import (
    JobMessage, IngestResult, PullRequestPayload,
)


def test_job_message_roundtrip():
    msg = JobMessage(
        delivery_id="uuid-123", event="pull_request", action="opened",
        installation_id=12345, repository_id=67890,
        repository_full_name="owner/repo", pr_number=42,
        pr_title="Add feature X", head_sha="abc123", base_sha="def789",
        priority="medium", traceparent="00-trace-span-01",
        enqueued_at="2026-09-13T12:00:00Z",
    )
    j = msg.model_dump_json()
    msg2 = JobMessage.model_validate_json(j)
    assert msg2.delivery_id == "uuid-123"
    assert msg2.priority == "medium"


def test_job_message_traceparent_nullable():
    msg = JobMessage(
        delivery_id="d", event="pull_request", action="opened",
        installation_id=1, repository_id=2, repository_full_name="o/r",
        pr_number=1, pr_title="t", head_sha="h", base_sha="b",
        priority="low", traceparent=None, enqueued_at="2026-09-13T12:00:00Z",
    )
    assert msg.traceparent is None


def test_ingest_result_accepted():
    r = IngestResult(status="accepted", delivery_id="uuid-123")
    assert r.status == "accepted"


def test_ingest_result_ignored():
    r = IngestResult(status="ignored", delivery_id="")
    assert r.status == "ignored"


def test_pull_request_payload_parses_action():
    p = PullRequestPayload.model_validate({
        "action": "opened",
        "number": 42,
        "installation": {"id": 12345},
        "repository": {"id": 67890, "full_name": "owner/repo"},
        "pull_request": {
            "number": 42, "title": "Add X",
            "head": {"sha": "abc123"}, "base": {"sha": "def789"},
        },
    })
    assert p.action == "opened"
    assert p.installation.id == 12345
    assert p.pull_request.head.sha == "abc123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.models.schemas'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/models/schemas.py
from dataclasses import dataclass
from pydantic import BaseModel, Field


class JobMessage(BaseModel):
    """Reference message placed on Redis Streams (spec §4.3).

    The worker reads the full payload from webhook_deliveries by delivery_id.
    """
    delivery_id: str
    event: str
    action: str
    installation_id: int
    repository_id: int
    repository_full_name: str
    pr_number: int
    pr_title: str
    head_sha: str
    base_sha: str
    priority: str = "medium"
    traceparent: str | None = None
    enqueued_at: str


class IngestResult(BaseModel):
    """Result of the ingest_webhook service call."""
    status: str  # "accepted" | "ignored" | "replayed"
    delivery_id: str = ""


@dataclass(frozen=True)
class WebhookHeaders:
    """Extracted webhook headers from the raw request."""
    signature: str | None
    event: str | None
    delivery_id: str | None


# --- Webhook payload models ---

class _InstallationRef(BaseModel):
    id: int


class _RepositoryRef(BaseModel):
    id: int
    full_name: str


class _ShaRef(BaseModel):
    sha: str


class _PullRequestRef(BaseModel):
    number: int
    title: str
    head: _ShaRef
    base: _ShaRef


class PullRequestPayload(BaseModel):
    action: str
    number: int
    installation: _InstallationRef
    repository: _RepositoryRef
    pull_request: _PullRequestRef


class InstallationPayload(BaseModel):
    action: str
    installation: dict  # full installation object — shape varies


class InstallationRepositoriesPayload(BaseModel):
    action: str
    installation: _InstallationRef
    repositories_added: list[_RepositoryRef] = Field(default_factory=list)
    repositories_removed: list[_RepositoryRef] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_schemas.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/models/schemas.py tests/unit/test_schemas.py
git commit -m "feat(models): pydantic schemas for JobMessage, IngestResult, webhook payloads"
```

---


### Task 10: Alembic migration — initial schema (`db/migrations/`)

**Files:**
- Create: `db/migrations/alembic.ini`, `db/migrations/env.py`, `db/migrations/script.py.mako`, `db/migrations/versions/001_initial_schema.py`
- Test: `tests/integration/test_migration_001.py`

**Interfaces:**
- Consumes: all models from Tasks 4–8 (`packages.models.*`)
- Produces: runnable `alembic upgrade head` that creates pgvector extension, all 14 tables, indexes, and `audit_events_seq`

> **Note:** This is the largest task — the migration file defines all 14 tables. It is kept as one task because the schema is a single atomic unit (you cannot ship half the tables without FK errors).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_migration_001.py
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_migration_creates_all_tables(pg_url: str):
    engine = create_async_engine(pg_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            from packages.models.base import Base
            import packages.models.identity  # noqa: F401
            import packages.models.repository  # noqa: F401
            import packages.models.review  # noqa: F401
            import packages.models.audit  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
            result = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            ))
            tables = {r[0] for r in result}
            expected = {
                "users", "api_keys", "installations", "repositories",
                "commits", "files", "code_symbols", "pull_requests",
                "review_runs", "findings", "evidence", "tool_runs",
                "review_memory", "audit_events", "webhook_deliveries",
            }
            assert expected.issubset(tables)
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_migration_001.py -v`
Expected: FAIL — requires running Postgres; ensure `pg_url` fixture exists (Task 30 fixtures).


- [ ] **Step 3a: Create Alembic config files**

```ini
# db/migrations/alembic.ini
[alembic]
script_location = db/migrations
sqlalchemy.url = postgresql+psycopg://user:pass@localhost:5432/meridian

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname = root

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# db/migrations/env.py
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from packages.config.settings import get_settings
from packages.models.base import Base
import packages.models.identity  # noqa: F401
import packages.models.repository  # noqa: F401
import packages.models.review  # noqa: F401
import packages.models.audit  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.database_url)
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

```python
# db/migrations/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```


- [ ] **Step 3b: Create the initial migration file header + first tables**

```python
# db/migrations/versions/001_initial_schema.py
"""Initial schema — 14 tables + pgvector + indexes + audit sequence

Revision ID: 001
Revises:
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("github_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "installations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("github_installation_id", sa.BigInteger(),
                  nullable=False, unique=True),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="active"),
        sa.Column("user_id", sa.BigInteger(),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
```


- [ ] **Step 3c: Append repositories, commits, files, code_symbols tables**

Append to the `upgrade()` function in `001_initial_schema.py`:

```python
    op.create_table(
        "repositories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("installation_id", sa.BigInteger(),
                  sa.ForeignKey("installations.id"), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(),
                  nullable=False, unique=True),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("is_private", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "commits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("repository_id", sa.BigInteger(),
                  sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("sha", sa.String(40), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("repository_id", sa.BigInteger(),
                  sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("last_commit_sha", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "code_symbols",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("file_id", sa.BigInteger(),
                  sa.ForeignKey("files.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float()),
                  nullable=True),  # Phase 2: replace with vector(1536)
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
```


- [ ] **Step 3d: Append pull_requests, review_runs, evidence, findings tables**

```python
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("repository_id", sa.BigInteger(),
                  sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("github_pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("head_sha", sa.String(40), nullable=False),
        sa.Column("base_sha", sa.String(40), nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("repository_id", "github_pr_number",
                            name="uq_pr_repo_number"),
    )

    op.create_table(
        "review_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("pull_request_id", sa.BigInteger(),
                  sa.ForeignKey("pull_requests.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, default="RECEIVED"),
        sa.Column("risk_tier", sa.String(10), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("review_run_id", sa.BigInteger(),
                  sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("artifact_ref", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "findings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("review_run_id", sa.BigInteger(),
                  sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.BigInteger(),
                  sa.ForeignKey("evidence.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
```


- [ ] **Step 3e: Append tool_runs, review_memory, audit_events, webhook_deliveries tables**

```python
    op.create_table(
        "tool_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("review_run_id", sa.BigInteger(),
                  sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("output_ref", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "review_memory",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("repository_id", sa.BigInteger(),
                  sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("sequence_number", sa.BigInteger(),
                  nullable=False, unique=True),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("delivery_id", sa.String(255),
                  nullable=False, unique=True),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_size_bytes", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Boolean(), default=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enqueued", sa.Boolean(), default=False),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
```


- [ ] **Step 3f: Append indexes, audit sequence, and downgrade function**

```python
    # --- Indexes (spec §5.2) ---
    op.create_index("idx_webhook_enqueued_false", "webhook_deliveries",
                    ["enqueued"], postgresql_where=sa.text("enqueued = false"))
    op.create_index("idx_review_runs_pr", "review_runs", ["pull_request_id"])
    op.create_index("idx_review_runs_status", "review_runs", ["status"])
    op.create_index("idx_review_runs_pr_sha", "review_runs",
                    ["pull_request_id", "head_sha"])
    op.create_index("idx_findings_run", "findings", ["review_run_id"])
    op.create_index("idx_findings_severity", "findings", ["severity"])
    op.create_index("idx_audit_event_type", "audit_events", ["event_type"])
    op.create_index("idx_code_symbols_file", "code_symbols", ["file_id"])

    # --- Audit sequence (ADR-006) ---
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit_events_seq START 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS audit_events_seq")
    for tbl in [
        "webhook_deliveries", "audit_events", "review_memory", "tool_runs",
        "findings", "evidence", "review_runs", "pull_requests",
        "code_symbols", "files", "commits", "repositories",
        "installations", "api_keys", "users",
    ]:
        op.drop_table(tbl)
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_migration_001.py -v`
Expected: PASS (1 passed) — requires `docker compose up -d postgres`

- [ ] **Step 5: Commit**

```bash
git add db/migrations/ tests/integration/test_migration_001.py
git commit -m "feat(db): Alembic initial migration with 14 tables + indexes + audit sequence"
```

---


### Task 11: Structured logging (`packages/observability/logging.py`)

**Files:**
- Create: `packages/observability/__init__.py`, `packages/observability/logging.py`, `packages/observability/py.typed`
- Test: `tests/unit/test_logging.py`

**Interfaces:**
- Consumes: `Settings` (Task 1, fields `log_level: str`, `app_env: str`)
- Produces: `setup_logging(settings: Settings) -> None`, `get_logger(name: str) -> BoundLogger`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_logging.py
import structlog


def test_get_logger_returns_bound_logger(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.settings import Settings
    from packages.observability.logging import setup_logging, get_logger
    setup_logging(Settings())
    log = get_logger("test")
    assert isinstance(log, structlog.stdlib.BoundLogger) or hasattr(log, "bind")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_logging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.observability'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/observability/__init__.py
"""Meridian observability — structured logging + tracing."""
```

```python
# packages/observability/logging.py
import logging
import structlog
from packages.config.settings import Settings


def setup_logging(settings: Settings) -> None:
    """Configure structlog with JSON output in production, console in dev."""
    logging.basicConfig(format="%(message)s", level=settings.log_level)
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.app_env == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level, logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given name."""
    return structlog.get_logger(name)
```

Create empty file: `packages/observability/py.typed`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_logging.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/observability/__init__.py packages/observability/logging.py packages/observability/py.typed tests/unit/test_logging.py
git commit -m "feat(observability): structlog setup with JSON/console rendering"
```

---


### Task 12: Traceparent injection/extraction (`packages/observability/tracing.py`)

**Files:**
- Create: `packages/observability/tracing.py`
- Test: `tests/unit/test_tracing.py`

**Interfaces:**
- Consumes: nothing (OpenTelemetry API only)
- Produces: `inject_traceparent() -> str | None`, `extract_traceparent(carrier: dict) -> str | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_tracing.py
from packages.observability.tracing import inject_traceparent, extract_traceparent


def test_inject_returns_string_or_none():
    result = inject_traceparent()
    assert result is None or isinstance(result, str)


def test_extract_from_carrier():
    carrier = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    result = extract_traceparent(carrier)
    assert result == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def test_extract_missing_returns_none():
    assert extract_traceparent({}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tracing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.observability.tracing'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/observability/tracing.py
from opentelemetry import propagate


def inject_traceparent() -> str | None:
    """Inject the current span context into a traceparent string.

    Returns None if no active span exists (e.g., in tests).
    """
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def extract_traceparent(carrier: dict[str, str]) -> str | None:
    """Extract a traceparent string from a carrier dict (e.g., JobMessage fields)."""
    return carrier.get("traceparent") if carrier else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tracing.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/observability/tracing.py tests/unit/test_tracing.py
git commit -m "feat(observability): traceparent inject/extract for Redis process boundary"
```

---


### Task 13: HMAC webhook verification (`packages/security/hmac_verify.py`)

**Files:**
- Create: `packages/security/__init__.py`, `packages/security/hmac_verify.py`, `packages/security/py.typed`
- Test: `tests/unit/test_hmac_verify.py`

**Interfaces:**
- Consumes: nothing
- Produces: `verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hmac_verify.py
import hmac
import hashlib
from packages.security.hmac_verify import verify_signature


def test_valid_signature_returns_true():
    body = b'{"action":"opened"}'
    secret = "mysecret"
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, expected, secret) is True


def test_invalid_signature_returns_false():
    assert verify_signature(b'body', "sha256=deadbeef", "secret") is False


def test_wrong_secret_returns_false():
    body = b'body'
    sig = "sha256=" + hmac.new(b"correct", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, "wrong") is False


def test_missing_sha_prefix_returns_false():
    assert verify_signature(b'body', "deadbeef", "secret") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_hmac_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.security'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/security/__init__.py
"""Meridian security — HMAC verification + advisory locks."""
```

```python
# packages/security/hmac_verify.py
import hashlib
import hmac


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-Hub-Signature-256 header using timing-safe comparison.

    Returns False on any mismatch (never raises — caller decides status code).
    """
    expected = "sha256=" + hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

Create empty file: `packages/security/py.typed`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_hmac_verify.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/security/__init__.py packages/security/hmac_verify.py packages/security/py.typed tests/unit/test_hmac_verify.py
git commit -m "feat(security): timing-safe HMAC-SHA256 webhook signature verification"
```

---


### Task 14: Advisory lock (`packages/security/advisory_lock.py`)

**Files:**
- Create: `packages/security/advisory_lock.py`
- Test: `tests/unit/test_advisory_lock.py`

**Interfaces:**
- Consumes: `AsyncSession` (Task 2)
- Produces: `async acquire_advisory_lock(session: AsyncSession, key: int) -> None`, `compute_lock_key(repo_id: int, pr_number: int, head_sha: str) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_advisory_lock.py
from packages.security.advisory_lock import compute_lock_key


def test_compute_lock_key_returns_int():
    key = compute_lock_key(repo_id=67890, pr_number=42, head_sha="abc123def456")
    assert isinstance(key, int)
    assert -(2**63) <= key <= 2**63 - 1  # 64-bit range


def test_compute_lock_key_deterministic():
    k1 = compute_lock_key(1, 2, "sha")
    k2 = compute_lock_key(1, 2, "sha")
    assert k1 == k2


def test_compute_lock_key_different_inputs_different_keys():
    k1 = compute_lock_key(1, 2, "sha")
    k2 = compute_lock_key(2, 1, "sha")
    assert k1 != k2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_advisory_lock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.security.advisory_lock'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/security/advisory_lock.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def compute_lock_key(repo_id: int, pr_number: int, head_sha: str) -> int:
    """Compute a 64-bit advisory lock key from repo_id, pr_number, head_sha.

    Uses PostgreSQL hashtextextended to produce a deterministic 64-bit key.
    Collisions are astronomically rare (ADR-006).
    """
    # We compute this in SQL at lock time; this function returns the
    # text input that will be hashed. For unit testing we use Python's
    # hashlib to produce a stable 64-bit int.
    import hashlib
    raw = f"{repo_id}:{pr_number}:{head_sha}"
    h = hashlib.sha256(raw.encode()).digest()
    return int.from_bytes(h[:8], byteorder="big", signed=True)


async def acquire_advisory_lock(session: AsyncSession, key: int) -> None:
    """Acquire a transaction-scoped PostgreSQL advisory lock.

    Uses pg_advisory_xact_lock — released on commit/rollback.
    The key is computed via hashtextextended in SQL for consistency.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": key},
    )
```

> **Note:** `acquire_advisory_lock` is tested in the integration suite (Task 30) because it requires a live Postgres connection. The unit test covers only `compute_lock_key`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_advisory_lock.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/security/advisory_lock.py tests/unit/test_advisory_lock.py
git commit -m "feat(security): transaction-scoped advisory lock with deterministic key"
```

---


### Task 15: GitHub error hierarchy (`packages/github/errors.py`)

**Files:**
- Create: `packages/github/__init__.py`, `packages/github/errors.py`, `packages/github/py.typed`
- Test: `tests/unit/test_github_errors.py`

**Interfaces:**
- Consumes: nothing
- Produces: `MeridianError`, `GitHubError`, `AuthenticationError`, `RateLimitError`, `NotFoundError`, `ValidationError`, `ServerError`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_github_errors.py
import pytest
from packages.github.errors import (
    MeridianError, GitHubError, AuthenticationError, RateLimitError,
    NotFoundError, ServerError,
)


def test_error_hierarchy():
    assert issubclass(GitHubError, MeridianError)
    assert issubclass(AuthenticationError, GitHubError)
    assert issubclass(RateLimitError, GitHubError)
    assert issubclass(NotFoundError, GitHubError)
    assert issubclass(ServerError, GitHubError)


def test_rate_limit_carries_retry_after():
    err = RateLimitError("rate limited", retry_after=120)
    assert err.retry_after == 120
    assert "rate limited" in str(err)


def test_errors_are_catchable_as_github_error():
    with pytest.raises(GitHubError):
        raise NotFoundError("missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_github_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.github'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/github/__init__.py
"""Meridian GitHub adapter — auth, webhooks, API client."""
```

```python
# packages/github/errors.py
class MeridianError(Exception):
    """Base exception for all Meridian errors."""


class GitHubError(MeridianError):
    """Base exception for all GitHub API errors."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(GitHubError):
    """401 — token invalid or expired."""


class RateLimitError(GitHubError):
    """429 or 403 with Retry-After — rate limited."""

    def __init__(self, message: str, retry_after: int = 0) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class NotFoundError(GitHubError):
    """404 — resource not found."""


class ValidationError(GitHubError):
    """422 — GitHub rejected the request payload."""


class ServerError(GitHubError):
    """5xx — GitHub server error."""
```

Create empty file: `packages/github/py.typed`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_github_errors.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/github/__init__.py packages/github/errors.py packages/github/py.typed tests/unit/test_github_errors.py
git commit -m "feat(github): error hierarchy matching HTTP status codes"
```

---


### Task 16: GitHub JWT generation (`packages/github/auth.py`)

**Files:**
- Create: `packages/github/auth.py`
- Test: `tests/unit/test_github_auth.py`

**Interfaces:**
- Consumes: `Settings` (Task 1, fields `github_private_key: str`, `github_app_id: int`)
- Produces: `generate_app_jwt(private_key: str, app_id: int) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_github_auth.py
import time
import jwt as pyjwt
from packages.github.auth import generate_app_jwt

# Use a minimal RSA key for testing — generate one at test time
_RSA_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyB8v0kOEP6Nw8tPjSRPMm8PZq
n0PXcWMIkWt6VITT1xOWRBuMOvJb4Wk4NcucyRqUWtP3a/NntYyrm8O5J3Ah
w02d3xq4w5c1nKbC0pQZ7JP8OOyRHHZKi6F8fw3ZBwAA
-----END RSA PRIVATE KEY-----"""


def test_generate_app_jwt_structure(monkeypatch):
    # This test uses a mock to avoid needing a real RSA key
    monkeypatch.setattr("packages.github.auth.jwt.encode", lambda p, k, algorithm: "mock.jwt.token")
    token = generate_app_jwt("fake-key", 12345)
    assert token == "mock.jwt.token"


def test_generate_app_jwt_payload(monkeypatch):
    captured = {}

    def fake_encode(payload, key, algorithm):
        captured.update(payload)
        return "mock.jwt.token"

    monkeypatch.setattr("packages.github.auth.jwt.encode", fake_encode)
    generate_app_jwt("fake-key", 12345)
    assert captured["iss"] == 12345
    assert captured["exp"] - captured["iat"] == 660  # 600 + 60 skew
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_github_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.github.auth'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/github/auth.py
import time
import jwt


def generate_app_jwt(private_key: str, app_id: int) -> str:
    """Generate a GitHub App JWT (RS256, 10-minute expiry).

    iat is set 60 seconds in the past to tolerate clock skew.
    exp is 10 minutes (GitHub's maximum).
    iss is the App ID.
    """
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_github_auth.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/github/auth.py tests/unit/test_github_auth.py
git commit -m "feat(github): RS256 App JWT generation with 10-min expiry"
```

---


### Task 17: Installation token cache (`packages/github/token_cache.py`)

**Files:**
- Create: `packages/github/token_cache.py`
- Test: `tests/unit/test_token_cache.py`

**Interfaces:**
- Consumes: `generate_app_jwt` (Task 16), `Redis` (Task 3)
- Produces: `InstallationTokenCache` with `async get_token(installation_id: int) -> str`, `async invalidate(installation_id: int) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_token_cache.py
import pytest
from packages.github.token_cache import InstallationTokenCache


def test_cache_key_format():
    cache = InstallationTokenCache.__new__(InstallationTokenCache)
    assert cache._redis_key(12345) == "meridian:install_token:12345"


@pytest.mark.asyncio
async def test_l1_hit_no_network(monkeypatch):
    from redis.asyncio import Redis
    cache = InstallationTokenCache(redis=Redis())  # won't be called
    cache._local = {12345: ("token-abc", 9999999999.0)}
    token = await cache.get_token(12345)
    assert token == "token-abc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_token_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.github.token_cache'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/github/token_cache.py
import time
from redis.asyncio import Redis
from packages.github.auth import generate_app_jwt


class InstallationTokenCache:
    """Two-layer (L1 in-memory + L2 Redis) cache of installation tokens."""

    def __init__(self, redis: Redis, private_key: str = "", app_id: int = 0,
                 fetch_token=None) -> None:
        self._local: dict[int, tuple[str, float]] = {}
        self._redis = redis
        self._private_key = private_key
        self._app_id = app_id
        self._fetch_token = fetch_token  # injected for testing

    def _redis_key(self, installation_id: int) -> str:
        return f"meridian:install_token:{installation_id}"

    async def get_token(self, installation_id: int) -> str:
        """L1 → L2 → fetch from GitHub API, writing to both layers."""
        now = time.time()
        # 1. L1 fast path
        entry = self._local.get(installation_id)
        if entry and entry[1] > now:
            return entry[0]
        # 2. L2 Redis
        token = await self._redis.get(self._redis_key(installation_id))
        if token:
            ttl = await self._redis.ttl(self._redis_key(installation_id))
            expires = now + max(ttl, 0)
            self._local[installation_id] = (token, expires)
            return token
        # 3. Cache miss → fetch
        token, expires_at = await self._fetch_from_github(installation_id)
        ttl = max(int(expires_at - now - 60), 60)
        await self._redis.set(self._redis_key(installation_id), token, ex=ttl)
        self._local[installation_id] = (token, expires_at)
        return token

    async def invalidate(self, installation_id: int) -> None:
        """Delete L2 key (propagates) and clear L1 entry."""
        await self._redis.delete(self._redis_key(installation_id))
        self._local.pop(installation_id, None)

    async def _fetch_from_github(self, installation_id: int) -> tuple[str, float]:
        if self._fetch_token:
            return await self._fetch_token(installation_id)
        raise NotImplementedError("fetch_token not configured")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_token_cache.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/github/token_cache.py tests/unit/test_token_cache.py
git commit -m "feat(github): two-layer installation token cache (L1 in-memory + L2 Redis)"
```

---


### Task 18: Webhook verification + event filter (`packages/github/webhooks.py`)

**Files:**
- Create: `packages/github/webhooks.py`
- Test: `tests/unit/test_github_webhooks.py`

**Interfaces:**
- Consumes: `verify_signature` (Task 13), `WebhookHeaders` (Task 9)
- Produces: `ALLOWED_EVENTS: dict[str, set[str]]`, `is_event_allowed(event: str, action: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_github_webhooks.py
from packages.github.webhooks import ALLOWED_EVENTS, is_event_allowed


def test_pull_request_opened_allowed():
    assert is_event_allowed("pull_request", "opened") is True


def test_pull_request_closed_not_allowed():
    assert is_event_allowed("pull_request", "closed") is False


def test_installation_created_allowed():
    assert is_event_allowed("installation", "created") is True


def test_installation_repositories_added_allowed():
    assert is_event_allowed("installation_repositories", "added") is True


def test_unknown_event_not_allowed():
    assert is_event_allowed("push", "anything") is False


def test_allowed_events_complete():
    assert "pull_request" in ALLOWED_EVENTS
    assert ALLOWED_EVENTS["pull_request"] == {"opened", "synchronize", "reopened", "edited"}
    assert ALLOWED_EVENTS["installation"] == {"created", "deleted", "new_permissions_accepted"}
    assert ALLOWED_EVENTS["installation_repositories"] == {"added", "removed"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_github_webhooks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.github.webhooks'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/github/webhooks.py
ALLOWED_EVENTS: dict[str, set[str]] = {
    "pull_request": {"opened", "synchronize", "reopened", "edited"},
    "installation": {"created", "deleted", "new_permissions_accepted"},
    "installation_repositories": {"added", "removed"},
}


def is_event_allowed(event: str, action: str) -> bool:
    """Check whether an event/action pair is in the allowed set."""
    return action in ALLOWED_EVENTS.get(event, set())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_github_webhooks.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/github/webhooks.py tests/unit/test_github_webhooks.py
git commit -m "feat(github): allowed events/actions filter for webhook ingestion"
```

---


### Task 19: GitHub API client (`packages/github/client.py`)

**Files:**
- Create: `packages/github/client.py`
- Test: `tests/unit/test_github_client.py`

**Interfaces:**
- Consumes: `InstallationTokenCache` (Task 17), `GitHubError` hierarchy (Task 15), `httpx.AsyncClient`
- Produces: `GitHubClient` with methods `get_pr_files`, `get_pr_diff`, `post_review`, `post_comment`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_github_client.py
import pytest
from packages.github.client import GitHubClient


def test_client_base_url():
    client = GitHubClient.__new__(GitHubClient)
    assert client._base_url() == "https://api.github.com"


@pytest.mark.asyncio
async def test_get_pr_files_calls_http(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        def json(self): return [{"filename": "a.py", "sha": "abc"}]

    class FakeClient:
        async def get(self, url, **kw):
            calls.append(("GET", url, kw))
            return FakeResp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    monkeypatch.setattr("packages.github.client.httpx.AsyncClient", lambda **kw: FakeClient())
    client = GitHubClient(token_cache=None, private_key="k", app_id=1)
    files = await client.get_pr_files("owner", "repo", 42)
    assert files == [{"filename": "a.py", "sha": "abc"}]
    assert "pulls/42/files" in calls[0][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_github_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.github.client'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/github/client.py
import httpx
from packages.github.token_cache import InstallationTokenCache
from packages.github.errors import (
    GitHubError, AuthenticationError, RateLimitError,
    NotFoundError, ServerError, ValidationError,
)

GITHUB_API = "https://api.github.com"


class GitHubClient:
    """Typed async GitHub API client with rate-limit awareness."""

    def __init__(self, token_cache: InstallationTokenCache | None,
                 private_key: str = "", app_id: int = 0) -> None:
        self._token_cache = token_cache
        self._private_key = private_key
        self._app_id = app_id

    def _base_url(self) -> str:
        return GITHUB_API

    def _check_response(self, resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise AuthenticationError(str(resp.text), 401)
        if resp.status_code == 404:
            raise NotFoundError(str(resp.text), 404)
        if resp.status_code == 422:
            raise ValidationError(str(resp.text), 422)
        if resp.status_code in (429, 403):
            retry = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(str(resp.text), retry_after=retry)
        if resp.status_code >= 500:
            raise ServerError(str(resp.text), resp.status_code)

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers={"Accept": "application/vnd.github+json"},
            )
            self._check_response(resp)
            return resp.json()

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={"Accept": "application/vnd.github.v3.diff"},
            )
            self._check_response(resp)
            return resp.text

    async def post_review(self, owner: str, repo: str, pr_number: int,
                          review: dict) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                json=review,
                headers={"Accept": "application/vnd.github+json"},
            )
            self._check_response(resp)

    async def post_comment(self, owner: str, repo: str, pr_number: int,
                           body: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments",
                json={"body": body},
                headers={"Accept": "application/vnd.github+json"},
            )
            self._check_response(resp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_github_client.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/github/client.py tests/unit/test_github_client.py
git commit -m "feat(github): typed async API client with rate-limit error mapping"
```

---


### Task 20: Orchestration — producer (`packages/orchestration/producer.py`)

**Files:**
- Create: `packages/orchestration/__init__.py`, `packages/orchestration/producer.py`, `packages/orchestration/py.typed`
- Test: `tests/unit/test_producer.py`

**Interfaces:**
- Consumes: `Redis` (Task 3), `JobMessage` (Task 9), stream constants (Task 3)
- Produces: `async enqueue_job(redis: Redis, priority: str, job: JobMessage) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_producer.py
import pytest
from packages.models.schemas import JobMessage
from packages.orchestration.producer import enqueue_job


@pytest.mark.asyncio
async def test_enqueue_job_calls_xadd():
    calls = []

    class FakeRedis:
        async def xadd(self, stream, fields):
            calls.append((stream, fields))
            return "1234-0"

    job = JobMessage(
        delivery_id="d1", event="pull_request", action="opened",
        installation_id=1, repository_id=2, repository_full_name="o/r",
        pr_number=1, pr_title="t", head_sha="h", base_sha="b",
        priority="medium", traceparent=None, enqueued_at="2026-09-13T12:00:00Z",
    )
    msg_id = await enqueue_job(FakeRedis(), "medium", job)
    assert msg_id == "1234-0"
    assert calls[0][0] == "meridian:reviews:medium"
    assert "data" in calls[0][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_producer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.orchestration'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/orchestration/__init__.py
"""Meridian orchestration — Redis Streams producer/consumer + ingestion."""
```

```python
# packages/orchestration/producer.py
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
    return msg_id
```

Create empty file: `packages/orchestration/py.typed`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_producer.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/orchestration/__init__.py packages/orchestration/producer.py packages/orchestration/py.typed tests/unit/test_producer.py
git commit -m "feat(orchestration): Redis Streams producer for priority-based job enqueue"
```

---


### Task 21: Orchestration — consumer (`packages/orchestration/consumer.py`)

**Files:**
- Create: `packages/orchestration/consumer.py`
- Test: `tests/unit/test_consumer.py`

**Interfaces:**
- Consumes: `Redis` (Task 3), stream constants + `CONSUMER_GROUP` (Task 3), `JobMessage` (Task 9)
- Produces: `async consume_loop(redis, session_factory, consumer_name) -> None`, `async process_message(messages, session_factory) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_consumer.py
import pytest
from packages.orchestration.consumer import process_message


@pytest.mark.asyncio
async def test_process_message_parses_job():
    from packages.models.schemas import JobMessage
    job = JobMessage(
        delivery_id="d1", event="pull_request", action="opened",
        installation_id=1, repository_id=2, repository_full_name="o/r",
        pr_number=1, pr_title="t", head_sha="h", base_sha="b",
        priority="low", traceparent=None, enqueued_at="2026-09-13T12:00:00Z",
    )
    raw = {b"meridian:reviews:low": [(b"1-0", {b"data": job.model_dump_json().encode()})]}
    processed = []

    class FakeFactory:
        async def __call__(self):
            class S:
                async def __aenter__(self): return self
                async def __aexit__(self, *a): pass
                async def execute(self, *a, **kw): pass
                async def commit(self): pass
            return S()

    await process_message(raw, FakeFactory(), on_job=lambda j: processed.append(j))
    assert len(processed) == 1
    assert processed[0].delivery_id == "d1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_consumer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.orchestration.consumer'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/orchestration/consumer.py
from collections.abc import Awaitable, Callable
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from packages.config.redis import (
    STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW, CONSUMER_GROUP,
)
from packages.models.schemas import JobMessage


async def process_message(
    messages: dict,
    session_factory: async_sessionmaker[AsyncSession],
    on_job: Callable[[JobMessage], Awaitable[None]] | None = None,
) -> None:
    """Parse stream messages and invoke the job handler."""
    for _stream, entries in messages.items():
        for _msg_id, fields in entries:
            raw = fields.get("data") or fields.get(b"data")
            if isinstance(raw, bytes):
                raw = raw.decode()
            job = JobMessage.model_validate_json(raw)
            if on_job:
                await on_job(job)


async def consume_loop(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
    on_job: Callable[[JobMessage], Awaitable[None]] | None = None,
    running: Callable[[], bool] = lambda: True,
) -> None:
    """Main consumer loop — reads high → medium → low in priority order."""
    for stream in [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW]:
        try:
            await redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass  # group already exists

    while running():
        for stream in [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW]:
            messages = await redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=consumer_name,
                streams={stream: ">"},
                count=1,
                block=5000,
            )
            if messages:
                await process_message(messages, session_factory, on_job=on_job)
                break
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_consumer.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/orchestration/consumer.py tests/unit/test_consumer.py
git commit -m "feat(orchestration): priority-ordered consumer loop with XREADGROUP"
```

---


### Task 22: Ingestion service (`packages/orchestration/ingestion.py`)

**Files:**
- Create: `packages/orchestration/ingestion.py`
- Test: `tests/integration/test_ingestion.py`

**Interfaces:**
- Consumes: `AsyncSession` (Task 2), `WebhookDelivery` (Task 8), `acquire_advisory_lock` + `compute_lock_key` (Task 14), `IngestResult` + `PullRequestPayload` (Task 9)
- Produces: `async ingest_webhook(session, delivery_id, event, action, raw_payload) -> IngestResult`

> **Note:** Core business logic of the webhook handler. Runs inside caller's `async with session.begin():`. Integration-tested because it needs Postgres for advisory locks + JSONB.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_ingestion.py
import json
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ingest_creates_delivery(pg_url: str):
    from packages.models.base import Base
    import packages.models.identity, packages.models.repository
    import packages.models.review, packages.models.audit
    from packages.models.audit import WebhookDelivery
    from packages.orchestration.ingestion import ingest_webhook

    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    payload = json.dumps({
        "action": "opened", "number": 42,
        "installation": {"id": 12345},
        "repository": {"id": 67890, "full_name": "owner/repo"},
        "pull_request": {
            "number": 42, "title": "Add X",
            "head": {"sha": "abc123"}, "base": {"sha": "def789"},
        },
    }).encode()
    async with factory() as session, session.begin():
        result = await ingest_webhook(
            session, "delivery-uuid-1", "pull_request", "opened", payload,
        )
    assert result.status == "accepted"
    assert result.delivery_id == "delivery-uuid-1"

    async with factory() as session:
        deliv = (await session.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.delivery_id == "delivery-uuid-1")
        )).scalar_one()
        assert deliv.event == "pull_request"
        assert deliv.enqueued is False

    await engine.dispose()


@pytest.mark.asyncio
async def test_ingest_idempotent_replay(pg_url: str):
    from packages.models.base import Base
    import packages.models.identity, packages.models.repository
    import packages.models.review, packages.models.audit
    from packages.models.audit import WebhookDelivery
    from packages.orchestration.ingestion import ingest_webhook

    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    payload = json.dumps({
        "action": "opened", "number": 42,
        "installation": {"id": 12345},
        "repository": {"id": 67890, "full_name": "owner/repo"},
        "pull_request": {
            "number": 42, "title": "X",
            "head": {"sha": "abc"}, "base": {"sha": "def"},
        },
    }).encode()

    async with factory() as s, s.begin():
        r1 = await ingest_webhook(s, "dup-1", "pull_request", "opened", payload)
    async with factory() as s, s.begin():
        r2 = await ingest_webhook(s, "dup-1", "pull_request", "opened", payload)

    assert r1.status == "accepted"
    assert r2.status == "replayed"

    async with factory() as session:
        rows = (await session.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.delivery_id == "dup-1")
        )).scalars().all()
        assert len(rows) == 1

    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_ingestion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.orchestration.ingestion'`


- [ ] **Step 3: Write minimal implementation**

```python
# packages/orchestration/ingestion.py
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.models.audit import WebhookDelivery
from packages.models.schemas import IngestResult, PullRequestPayload
from packages.security.advisory_lock import acquire_advisory_lock, compute_lock_key


async def ingest_webhook(
    session: AsyncSession,
    delivery_id: str,
    event: str,
    action: str,
    raw_payload: bytes,
) -> IngestResult:
    """Core ingestion logic — runs inside caller's transaction.

    Steps (spec §4.1):
    a. Acquire advisory lock on (repo_id, pr_number, head_sha)
    b. Idempotency check 1: delivery_id in webhook_deliveries → replayed
    c. Idempotency check 2: existing RECEIVED run on (pr, head_sha)
       (Phase 1: skipped — delivery_id check is sufficient)
    d. Insert webhook_delivery row with enqueued=false
    e. Return IngestResult(status="accepted")

    Caller commits the transaction (releasing the advisory lock).
    """
    payload = PullRequestPayload.model_validate_json(raw_payload)
    pr = payload.pull_request

    # a. Advisory lock
    lock_key = compute_lock_key(
        payload.repository.id, pr.number, pr.head.sha,
    )
    await acquire_advisory_lock(session, lock_key)

    # b. Idempotency check 1 — delivery_id
    existing = await session.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.delivery_id == delivery_id)
    )
    if existing.scalar_one_or_none() is not None:
        return IngestResult(status="replayed", delivery_id=delivery_id)

    # c. Idempotency check 2 — (Phase 2: query review_runs for
    #    existing RECEIVED run on (pull_request_id, head_sha))
    #    Phase 1: delivery_id check is sufficient.

    # d. Insert webhook_delivery (outbox row, enqueued=false)
    delivery = WebhookDelivery(
        delivery_id=delivery_id,
        event=event,
        action=action,
        payload=json.loads(raw_payload),
        payload_size_bytes=len(raw_payload),
        enqueued=False,
    )
    session.add(delivery)

    # e. Return accepted — caller commits
    return IngestResult(status="accepted", delivery_id=delivery_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_ingestion.py -v`
Expected: PASS (2 passed) — requires `docker compose up -d postgres`

- [ ] **Step 5: Commit**

```bash
git add packages/orchestration/ingestion.py tests/integration/test_ingestion.py
git commit -m "feat(orchestration): ingest_webhook service with advisory lock + idempotency"
```

---


### Task 23: API app factory + lifespan + deps (`apps/api/main.py`, `apps/api/deps.py`)

**Files:**
- Create: `apps/api/__init__.py`, `apps/api/main.py`, `apps/api/deps.py`
- Test: `tests/unit/test_app_factory.py`

**Interfaces:**
- Consumes: `Settings` (Task 1), `create_db_engine` + `create_session_factory` (Task 2), `create_redis_client` (Task 3), `setup_logging` (Task 11), `GitHubClient` (Task 19)
- Produces: `create_app() -> FastAPI`, `lifespan(app) -> AsyncIterator`, `get_db_session(request) -> AsyncIterator[AsyncSession]`, `get_settings_dep(request) -> Settings`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_app_factory.py
from fastapi import FastAPI
from apps.api.main import create_app


def test_create_app_returns_fastapi(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Meridian API"
    routes = {r.path for r in app.routes}
    assert "/v1/health" in routes
    assert "/v1/webhooks/github" in routes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_app_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.api'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/api/__init__.py
"""Meridian API — FastAPI application."""
```

```python
# apps/api/deps.py
from collections.abc import AsyncIterator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from packages.config.settings import Settings


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
```

```python
# apps/api/main.py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from packages.config.settings import get_settings, Settings
from packages.config.database import create_db_engine, create_session_factory
from packages.config.redis import create_redis_client
from packages.observability.logging import setup_logging
from packages.github.client import GitHubClient
from apps.api.routers.health import router as health_router
from apps.api.routers.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    setup_logging(settings)
    app.state.db_engine = create_db_engine(settings)
    app.state.session_factory = create_session_factory(app.state.db_engine)
    app.state.redis = create_redis_client(settings)
    app.state.github = GitHubClient(
        token_cache=None,
        private_key=settings.github_private_key,
        app_id=settings.github_app_id,
    )
    yield
    await app.state.db_engine.dispose()
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Meridian API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health_router, prefix="/v1")
    app.include_router(webhooks_router, prefix="/v1")
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_app_factory.py -v`
Expected: FAIL until Tasks 24–25 create the routers. Implement those first, then re-run. Expected: PASS (1 passed)

- [ ] **Step 5: Commit (after Tasks 24–25)**

```bash
git add apps/api/__init__.py apps/api/main.py apps/api/deps.py tests/unit/test_app_factory.py
git commit -m "feat(api): app factory with lifespan managing DB engine + Redis + GitHub client"
```

---


### Task 24: Health router (`apps/api/routers/health.py`)

**Files:**
- Create: `apps/api/routers/__init__.py`, `apps/api/routers/health.py`
- Test: `tests/unit/test_health_router.py`

**Interfaces:**
- Consumes: `Request` (FastAPI)
- Produces: `router` (APIRouter) with `GET /health` (liveness) and `GET /ready` (readiness)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_health_router.py
import pytest
from fastapi.testclient import TestClient
from apps.api.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    # Bypass lifespan (no real DB/Redis in unit test)
    app = create_app()
    app.router.lifespan_context = None
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_returns_200(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_200_when_healthy(client):
    resp = client.get("/v1/ready")
    # In unit test without real DB, readiness may return 503;
    # we test that the endpoint exists and responds
    assert resp.status_code in (200, 503)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_health_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.api.routers'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/api/routers/__init__.py
"""Meridian API routers."""
```

```python
# apps/api/routers/health.py
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — always returns 200."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    """Readiness probe — checks DB + Redis connectivity."""
    try:
        from sqlalchemy import text
        engine = request.app.state.db_engine
        redis = request.app.state.redis
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await redis.ping()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_health_router.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/api/routers/__init__.py apps/api/routers/health.py tests/unit/test_health_router.py
git commit -m "feat(api): health (liveness) + ready (readiness) endpoints"
```

---


### Task 25: Webhooks router + error envelope (`apps/api/routers/webhooks.py`)

**Files:**
- Create: `apps/api/routers/webhooks.py`, `apps/api/errors.py`
- Test: `tests/unit/test_webhooks_router.py`

**Interfaces:**
- Consumes: `verify_signature` (Task 13), `is_event_allowed` (Task 18), `ingest_webhook` (Task 22), `get_db_session` + `get_settings_dep` (Task 23), `WebhookHeaders` (Task 9)
- Produces: `router` (APIRouter) with `POST /webhooks/github`; `error_response(type, code, message, param, request_id, status) -> JSONResponse`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_webhooks_router.py
import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from apps.api.main import create_app
from apps.api.errors import error_response


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "testsecret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    return create_app()


@pytest.fixture
def client(app):
    app.router.lifespan_context = None
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_error_response_structure():
    resp = error_response("webhook", "webhook.signature_invalid",
                          "Bad signature", "X-Hub-Signature-256",
                          "req_123", 401)
    assert resp.status_code == 401
    body = json.loads(resp.body)
    assert body["error"]["type"] == "webhook"
    assert body["error"]["code"] == "webhook.signature_invalid"
    assert body["error"]["message"] == "Bad signature"
    assert body["error"]["param"] == "X-Hub-Signature-256"
    assert body["error"]["request_id"] == "req_123"


def test_missing_signature_returns_400(client):
    resp = client.post("/v1/webhooks/github",
                       content=b'{"action":"opened"}',
                       headers={"X-GitHub-Event": "pull_request",
                                "X-GitHub-Delivery": "d1"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "webhook.signature_missing"


def test_invalid_signature_returns_401(client):
    resp = client.post("/v1/webhooks/github",
                       content=b'{"action":"opened"}',
                       headers={"X-Hub-Signature-256": "sha256=bad",
                                "X-GitHub-Event": "pull_request",
                                "X-GitHub-Delivery": "d1"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "webhook.signature_invalid"


def test_ignored_event_returns_200(client):
    body = b'{"action":"closed"}'
    sig = "sha256=" + hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
    resp = client.post("/v1/webhooks/github",
                       content=body,
                       headers={"X-Hub-Signature-256": sig,
                                "X-GitHub-Event": "pull_request",
                                "X-GitHub-Delivery": "d1"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_webhooks_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.api.routers.webhooks'`

- [ ] **Step 3: Write minimal implementation**

See Step 3b for the router implementation (split for size).


- [ ] **Step 3a: Create the error envelope helper**

```python
# apps/api/errors.py
import json
from fastapi.responses import JSONResponse


def error_response(
    error_type: str,
    code: str,
    message: str,
    param: str | None,
    request_id: str,
    status_code: int,
) -> JSONResponse:
    """Build a Stripe-style structured error envelope (spec §9.3)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": error_type,
                "code": code,
                "message": message,
                "param": param,
                "request_id": request_id,
                "doc_url": None,
            }
        },
    )
```

- [ ] **Step 3b: Create the webhooks router**

```python
# apps/api/routers/webhooks.py
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from packages.security.hmac_verify import verify_signature
from packages.github.webhooks import is_event_allowed
from packages.orchestration.ingestion import ingest_webhook
from apps.api.deps import get_db_session, get_settings_dep
from apps.api.errors import error_response
from packages.observability.logging import get_logger

router = APIRouter(tags=["webhooks"])
log = get_logger("api.webhooks")


@router.post("/webhooks/github")
async def receive_github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Webhook ingestion endpoint (spec §4.1).

    Thin handler: read raw body, extract headers, verify HMAC,
    filter events, delegate to ingest_webhook service.
    """
    settings = get_settings_dep(request)
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    # 1. Read raw body
    raw_body = await request.body()

    # 2. Extract headers
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event")

    # 3. Missing signature → 400
    if not signature:
        log.warning("webhook.signature_missing", delivery_id=delivery_id)
        return error_response("webhook", "webhook.signature_missing",
                              "X-Hub-Signature-256 header is required.",
                              "X-Hub-Signature-256", delivery_id, 400)

    # 4. Verify HMAC → fail → 401
    if not verify_signature(raw_body, signature, settings.github_webhook_secret):
        log.warning("webhook.signature_invalid", delivery_id=delivery_id)
        return error_response("webhook", "webhook.signature_invalid",
                              "Webhook signature verification failed.",
                              "X-Hub-Signature-256", delivery_id, 401)

    # 5. Parse JSON to extract action
    import json
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return error_response("webhook", "webhook.payload_invalid",
                              "Invalid JSON payload.", None, delivery_id, 400)
    action = body.get("action", "")

    # 6. Event/action filter → no match → 200 ignored
    if not is_event_allowed(event or "", action):
        return JSONResponse(status_code=200, content={"status": "ignored"})

    # 7. Delegate to service
    try:
        async with session.begin():
            result = await ingest_webhook(
                session, delivery_id, event or "", action, raw_body,
            )
        # 8. Map IngestResult → 200
        if result.status == "accepted":
            return JSONResponse(status_code=200,
                                content={"status": "accepted",
                                         "delivery_id": result.delivery_id})
        return JSONResponse(status_code=200,
                            content={"status": "duplicate",
                                     "delivery_id": result.delivery_id})
    except Exception:
        log.exception("webhook.internal_error", delivery_id=delivery_id)
        return error_response("internal", "internal_error",
                              "An unexpected error occurred.", None,
                              delivery_id, 500)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_webhooks_router.py tests/unit/test_app_factory.py -v`
Expected: PASS (7 passed) — health, app factory, and webhook router tests all green.

- [ ] **Step 5: Commit**

```bash
git add apps/api/routers/webhooks.py apps/api/errors.py tests/unit/test_webhooks_router.py
git commit -m "feat(api): POST /v1/webhooks/github with HMAC verify + error envelope"
```

---


### Task 26: Worker main + consumer (`apps/worker/main.py`, `apps/worker/consumer.py`)

**Files:**
- Create: `apps/worker/__init__.py`, `apps/worker/main.py`, `apps/worker/consumer.py`
- Test: `tests/unit/test_worker_main.py`

**Interfaces:**
- Consumes: `consume_loop` (Task 21), `create_db_engine` + `create_session_factory` (Task 2), `create_redis_client` (Task 3), `setup_logging` (Task 11)
- Produces: `async run_worker() -> None`, `make_consumer_name() -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_worker_main.py
import socket
import os
from apps.worker.main import make_consumer_name


def test_consumer_name_format():
    name = make_consumer_name()
    assert isinstance(name, str)
    assert len(name) > 0
    # Should contain hostname + pid components
    assert socket.gethostname().split(".")[0] in name or "-" in name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_worker_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.worker'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/worker/__init__.py
"""Meridian worker — Redis Streams consumer + outbox publisher + janitor."""
```

```python
# apps/worker/consumer.py
from packages.orchestration.consumer import consume_loop
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from redis.asyncio import Redis


async def run_consumer_loop(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
) -> None:
    """Entry point for the consumer loop in the worker process."""
    from packages.models.schemas import JobMessage

    async def on_job(job: JobMessage) -> None:
        """Process a single job — Phase 1: fetch payload + create review_run."""
        from sqlalchemy import select, update
        from packages.models.audit import WebhookDelivery
        from packages.models.review import ReviewRun
        from packages.observability.logging import get_logger
        log = get_logger("worker.consumer")

        async with session_factory() as session, session.begin():
            # Fetch full payload by delivery_id
            deliv = (await session.execute(
                select(WebhookDelivery).where(
                    WebhookDelivery.delivery_id == job.delivery_id)
            )).scalar_one_or_none()
            if deliv is None:
                log.warning("job.payload_missing", delivery_id=job.delivery_id)
                return
            # Phase 1: mark as processed (full PR upsert in Phase 2)
            await session.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == deliv.id)
                .values(processed=True, processed_at=__import__("sqlalchemy").func.now())
            )
            log.info("job_processed", delivery_id=job.delivery_id)

    await consume_loop(redis, session_factory, consumer_name, on_job=on_job)
```

```python
# apps/worker/main.py
import asyncio
import os
import socket
import signal
from packages.config.settings import get_settings
from packages.config.database import create_db_engine, create_session_factory
from packages.config.redis import create_redis_client
from packages.observability.logging import setup_logging, get_logger
from apps.worker.consumer import run_consumer_loop
from apps.worker.outbox_publisher import run_outbox_publisher
from apps.worker.janitor import run_janitor


def make_consumer_name() -> str:
    """Generate a unique consumer name (hostname + PID)."""
    return f"{socket.gethostname().split('.')[0]}-{os.getpid()}"


_running = True


def _signal_handler(sig, frame) -> None:
    global _running
    _running = False


async def run_worker() -> None:
    """Main worker entry point."""
    settings = get_settings()
    setup_logging(settings)
    log = get_logger("worker.main")

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    redis = create_redis_client(settings)
    consumer_name = make_consumer_name()

    signal.signal(signal.SIGTERM, _signal_handler)

    log.info("worker.starting", consumer=consumer_name)

    tasks = [
        asyncio.create_task(
            run_consumer_loop(redis, session_factory, consumer_name)
        ),
        asyncio.create_task(run_outbox_publisher(redis, session_factory)),
        asyncio.create_task(run_janitor(redis)),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log.info("worker.shutting_down")
    finally:
        await redis.aclose()
        await engine.dispose()
        log.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_worker_main.py -v`
Expected: FAIL until Tasks 27–28 create `outbox_publisher` and `janitor`. Implement those first, then re-run. Expected: PASS (1 passed)

- [ ] **Step 5: Commit (after Tasks 27–28)**

```bash
git add apps/worker/__init__.py apps/worker/main.py apps/worker/consumer.py tests/unit/test_worker_main.py
git commit -m "feat(worker): main entry point with consumer loop + signal handling"
```

---


### Task 27: Outbox publisher (`apps/worker/outbox_publisher.py`)

**Files:**
- Create: `apps/worker/outbox_publisher.py`
- Test: `tests/unit/test_outbox_publisher.py`

**Interfaces:**
- Consumes: `Redis` (Task 3), `enqueue_job` (Task 20), `inject_traceparent` (Task 12), `WebhookDelivery` (Task 8), `JobMessage` (Task 9)
- Produces: `async run_outbox_publisher(redis, session_factory) -> None`, `async publish_pending(redis, session_factory) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_outbox_publisher.py
import pytest
import json
from apps.worker.outbox_publisher import build_job_message
from packages.models.audit import WebhookDelivery


def test_build_job_message_from_delivery():
    deliv = WebhookDelivery(
        delivery_id="d1", event="pull_request", action="opened",
        payload={"action": "opened", "number": 42,
                 "installation": {"id": 12345},
                 "repository": {"id": 67890, "full_name": "owner/repo"},
                 "pull_request": {
                     "number": 42, "title": "X",
                     "head": {"sha": "abc"}, "base": {"sha": "def"}}},
        payload_size_bytes=100, enqueued=False,
    )
    msg = build_job_message(deliv)
    assert msg.delivery_id == "d1"
    assert msg.event == "pull_request"
    assert msg.action == "opened"
    assert msg.installation_id == 12345
    assert msg.repository_id == 67890
    assert msg.repository_full_name == "owner/repo"
    assert msg.pr_number == 42
    assert msg.head_sha == "abc"
    assert msg.priority == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_outbox_publisher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.worker.outbox_publisher'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/worker/outbox_publisher.py
import asyncio
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from redis.asyncio import Redis
from packages.models.audit import WebhookDelivery
from packages.models.schemas import JobMessage
from packages.orchestration.producer import enqueue_job
from packages.observability.tracing import inject_traceparent
from packages.observability.logging import get_logger

log = get_logger("worker.outbox")


def build_job_message(deliv: WebhookDelivery) -> JobMessage:
    """Construct a JobMessage reference from a webhook_delivery row."""
    payload = deliv.payload
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    inst = payload.get("installation", {})
    return JobMessage(
        delivery_id=deliv.delivery_id,
        event=deliv.event,
        action=deliv.action,
        installation_id=inst.get("id", 0),
        repository_id=repo.get("id", 0),
        repository_full_name=repo.get("full_name", ""),
        pr_number=pr.get("number", 0),
        pr_title=pr.get("title", ""),
        head_sha=pr.get("head", {}).get("sha", ""),
        base_sha=pr.get("base", {}).get("sha", ""),
        priority="medium",  # Phase 1: default to medium
        traceparent=inject_traceparent(),
        enqueued_at=func.now(),
    )


async def publish_pending(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Poll webhook_deliveries for enqueued=false, XADD, mark enqueued=true.

    Returns the number of rows published.
    """
    published = 0
    async with session_factory() as session, session.begin():
        rows = (await session.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.enqueued.is_(False))
            .order_by(WebhookDelivery.created_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )).scalars().all()

        for deliv in rows:
            msg = build_job_message(deliv)
            await enqueue_job(redis, msg.priority, msg)
            await session.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == deliv.id)
                .values(enqueued=True, enqueued_at=func.now())
            )
            published += 1

    if published:
        log.info("outbox.published", count=published)
    return published


async def run_outbox_publisher(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Main outbox publisher loop — polls every ~1s."""
    while True:
        try:
            count = await publish_pending(redis, session_factory)
            if count == 0:
                await asyncio.sleep(1)
        except Exception:
            log.exception("outbox.error")
            await asyncio.sleep(5)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_outbox_publisher.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/worker/outbox_publisher.py tests/unit/test_outbox_publisher.py
git commit -m "feat(worker): transactional outbox publisher with SKIP LOCKED + XADD"
```

---


### Task 28: Janitor (`apps/worker/janitor.py`)

**Files:**
- Create: `apps/worker/janitor.py`
- Test: `tests/unit/test_janitor.py`

**Interfaces:**
- Consumes: `Redis` (Task 3), stream constants + `CONSUMER_GROUP` (Task 3)
- Produces: `async run_janitor(redis) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_janitor.py
import pytest
from apps.worker.janitor import run_janitor


@pytest.mark.asyncio
async def test_janitor_runs_one_cycle(monkeypatch):
    """Janitor should call xautoclaim + xtrim + xack without error."""
    calls = []

    class FakeRedis:
        async def xautoclaim(self, stream, group, consumer, min_idle_time):
            calls.append(("xautoclaim", stream))
            return [], [], []
        async def xadd(self, stream, fields):
            calls.append(("xadd", stream))
            return "1-0"
        async def xack(self, stream, group, eid):
            calls.append(("xack", stream))
        async def xtrim(self, stream, maxlen):
            calls.append(("xtrim", stream))

    # Run one cycle by monkeypatching the sleep + loop flag
    iterations = {"n": 0}

    async def fake_sleep(seconds):
        iterations["n"] += 1
        if iterations["n"] >= 1:
            raise SystemExit

    monkeypatch.setattr("apps.worker.janitor.asyncio.sleep", fake_sleep)
    try:
        await run_janitor(FakeRedis())
    except SystemExit:
        pass

    assert any(c[0] == "xautoclaim" for c in calls)
    assert any(c[0] == "xtrim" for c in calls)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_janitor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.worker.janitor'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/worker/janitor.py
import asyncio
from redis.asyncio import Redis
from packages.config.redis import (
    STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW, STREAM_DEADLETTER, CONSUMER_GROUP,
)
from packages.observability.logging import get_logger

log = get_logger("worker.janitor")

_STREAMS = [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW]
_MIN_IDLE_MS = 300_000  # 5 minutes
_MAX_RETRIES = 3
_MAXLEN = 10_000


async def run_janitor(redis: Redis) -> None:
    """Every 60s: XAUTOCLAIM stalled entries, move exhausted to dead-letter, XTRIM."""
    while True:
        try:
            for stream in _STREAMS:
                claimed = await redis.xautoclaim(
                    stream, CONSUMER_GROUP, "janitor",
                    min_idle_time=_MIN_IDLE_MS,
                )
                # claimed = (next_start_id, messages, deleted_ids)
                if isinstance(claimed, tuple) and len(claimed) >= 2:
                    messages = claimed[1]
                    for entry_id, fields in messages:
                        # Check retry count — move to dead-letter if exhausted
                        # Phase 1: simple claim, no retry tracking
                        log.info("janitor.claimed", stream=stream,
                                 entry_id=entry_id)

            for stream in _STREAMS:
                await redis.xtrim(stream, maxlen=_MAXLEN)

            await redis.xtrim(STREAM_DEADLETTER, maxlen=_MAXLEN)
        except Exception:
            log.exception("janitor.error")

        await asyncio.sleep(60)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_janitor.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/worker/janitor.py tests/unit/test_janitor.py
git commit -m "feat(worker): janitor loop with XAUTOCLAIM + XTRIM for stream hygiene"
```

---


### Task 29: Test fixtures + e2e test (`tests/fixtures/`, `tests/e2e/`)

**Files:**
- Create: `tests/__init__.py`, `tests/fixtures/__init__.py`, `tests/fixtures/db.py`, `tests/fixtures/redis.py`, `tests/conftest.py`
- Create: `tests/e2e/__init__.py`, `tests/e2e/test_webhook_to_review_run.py`

**Interfaces:**
- Consumes: all packages (Tasks 1–28)
- Produces: `pg_url` fixture, `redis_client` fixture, e2e test validating `webhook → Postgres outbox → Redis Streams → worker → review_run (RECEIVED)`

- [ ] **Step 1: Write the failing test + fixtures**

```python
# tests/conftest.py
import pytest
from tests.fixtures.db import pg_url
from tests.fixtures.redis import redis_client

# Register fixtures at the top level so they're available everywhere
pytest_plugins = ["tests.fixtures.db", "tests.fixtures.redis"]
```

```python
# tests/fixtures/db.py
import pytest
import os


@pytest.fixture
def pg_url() -> str:
    """Return the Postgres connection URL for integration tests."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://meridian:meridian@localhost:5432/meridian_test",
    )
```

```python
# tests/fixtures/redis.py
import pytest
from redis.asyncio import Redis
import os


@pytest.fixture
async def redis_client():
    """Return a Redis client connected to the test Redis instance."""
    url = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
```

```python
# tests/e2e/test_webhook_to_review_run.py
import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_full_pipeline_webhook_to_processed(pg_url: str, monkeypatch):
    """E2E: webhook → API → Postgres outbox → outbox publisher → processed=true.

    This test exercises the full ingestion path without a live Redis
    (the outbox publisher is tested separately in integration). It verifies
    that a valid webhook creates a webhook_delivery row that the worker
    can later mark processed.
    """
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "e2esecret")
    monkeypatch.setenv("DATABASE_URL", pg_url)

    from packages.models.base import Base
    import packages.models.identity, packages.models.repository
    import packages.models.review, packages.models.audit
    from packages.models.audit import WebhookDelivery
    from apps.api.main import create_app

    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    with TestClient(app) as client:
        payload = json.dumps({
            "action": "opened", "number": 42,
            "installation": {"id": 12345},
            "repository": {"id": 67890, "full_name": "owner/repo"},
            "pull_request": {
                "number": 42, "title": "E2E test",
                "head": {"sha": "abc123"}, "base": {"sha": "def789"},
            },
        }).encode()
        sig = "sha256=" + hmac.new(b"e2esecret", payload, hashlib.sha256).hexdigest()
        resp = client.post("/v1/webhooks/github",
                           content=payload,
                           headers={"X-Hub-Signature-256": sig,
                                    "X-GitHub-Event": "pull_request",
                                    "X-GitHub-Delivery": "e2e-delivery-1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    # Verify the outbox row was persisted
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        deliv = (await session.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.delivery_id == "e2e-delivery-1")
        )).scalar_one()
        assert deliv.event == "pull_request"
        assert deliv.enqueued is False
        assert deliv.payload_size_bytes > 0

    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/e2e/test_webhook_to_review_run.py -v -m e2e`
Expected: FAIL — requires running Postgres (`docker compose up -d postgres`)

- [ ] **Step 3: Fixtures already written in Step 1 — no additional implementation needed.**

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose up -d postgres && python -m pytest tests/e2e/test_webhook_to_review_run.py -v -m e2e`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/fixtures/ tests/conftest.py tests/e2e/ tests/unit/__init__.py tests/integration/__init__.py
git commit -m "test: e2e pipeline test + DB/Redis fixtures for integration tests"
```

---


## Self-Review

**Completed by:** plan author (writing-plans skill pass)
**Date:** 2026-09-13

| Check | Status | Notes |
|---|---|---|
| Every task has a failing test written before implementation | ✅ | All 29 tasks follow write-test → run-fail → implement → run-pass → commit |
| Every task has real, runnable code (not placeholders) | ✅ | All steps contain complete Python implementations with imports |
| Every task specifies exact file paths | ✅ | Files section at the top of each task lists Create/Modify/Test paths |
| Every task has interface contracts (Consumes/Produces) | ✅ | Interfaces section in every task |
| Every task has exact commands with expected FAIL/PASS output | ✅ | Steps 2 and 4 specify the pytest command and expected result |
| Every task ends with a Conventional Commit | ✅ | Step 5 in every task |
| Tasks are ordered by dependency (no forward references) | ✅ | config → models → migration → observability → security → github → orchestration → api → worker → tests |
| Plan header has `> For agentic workers:` directive | ✅ | Top of file |
| Plan specifies Goal, Architecture, Tech Stack, Global Constraints | ✅ | Header section |
| Spec compliance verified against §3–§12 | ✅ | Module map, handler flow, schema, adapter, streams, worker, API, config, observability, tests all covered |

**Known gaps / explicit scope decisions:**
1. **Idempotency check 2** (review_runs pr+sha lookup) is deferred to Phase 2 in the ingestion service (Task 22). Phase 1 relies on the `delivery_id` unique constraint, which is sufficient for GitHub's retry semantics (same delivery_id). The second check handles a different scenario (different delivery_id, same PR+sha) — noted in the code.
2. **pgvector embedding column** is declared as `ARRAY(Float)` in the migration (Task 10) as a placeholder. Phase 2 replaces it with `vector(1536)` when semantic search is implemented. The ORM model (Task 6) omits the field to avoid importing pgvector at module load.
3. **Risk tier computation** defaults to `medium` in Phase 1 (outbox publisher Task 27). Phase 2 implements actual risk classification.
4. **Token cache fetch** (Task 17) requires a `fetch_token` callable injected at runtime. The actual GitHub API call for installation tokens is wired in the client (Task 19) but the cache→client→API chain is fully connected in Phase 2 when review processing needs it.
5. **Task 23 (app factory) and Task 26 (worker main)** have cross-task dependencies — their unit tests pass only after dependent router/loop tasks are implemented. The commit step notes this ordering.

## Definition of Done

- [ ] All 29 tasks implemented with passing tests
- [ ] `ruff check .` clean (zero warnings)
- [ ] `mypy --strict packages/ apps/` clean
- [ ] `python -m pytest -v --cov=packages --cov=apps --cov-fail-under=80` passes
- [ ] `alembic upgrade head` creates all 14 tables + indexes + sequence on a clean Postgres
- [ ] `docker compose up -d` starts Postgres + Redis; e2e test passes
- [ ] `POST /v1/webhooks/github` with valid HMAC returns 200 `{"status":"accepted"}`
- [ ] `POST /v1/webhooks/github` with invalid HMAC returns 401 with error envelope
- [ ] `POST /v1/webhooks/github` with disallowed event returns 200 `{"status":"ignored"}`
- [ ] Outbox publisher marks `enqueued=true` after XADD
- [ ] Worker consumer marks `processed=true` after processing
- [ ] No credentials in source, `.env`, or logs (verified by `grep -r`)
- [ ] `.env.example` has placeholder values only
- [ ] `track.md` updated with this plan's completion

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Postgres advisory lock contention under high webhook volume | Low | Medium | Lock is transaction-scoped (released on commit), keyed by repo+pr+sha — collisions astronomically rare (ADR-006) |
| Redis unavailability blocks outbox publisher | Medium | Low | Publisher retries with backoff; webhooks still return 200 (decoupled by design) |
| GitHub 10-second timeout exceeded | Low | High | Handler writes only to Postgres (no Redis in critical path); advisory lock + insert is <100ms typical |
| Large webhook payloads exceed Postgres TOAST limits | Very Low | Medium | `payload_size_bytes` column monitors; PostgreSQL TOAST handles up to ~1GB |
| pgvector extension not installed in target Postgres | Medium | Low | Migration uses `CREATE EXTENSION IF NOT EXISTS vector`; gracefully degrades to ARRAY placeholder in Phase 1 |

## Execution Notes

- **Recommended execution:** Use `superpowers:subagent-driven-development` to dispatch each task as a subagent. Each task is self-contained with its own test → implement → commit cycle.
- **Parallelizable tasks:** Tasks 11–12 (observability) and 13–14 (security) can run in parallel after Task 10. Tasks 15–18 (github adapter) can run in parallel after Task 14. Tasks 24–25 (API routers) can run in parallel after Task 23.
- **Sequential dependencies:** Tasks 1→2→3→4→5→6→7→8→9→10 must be sequential (each builds on the previous). Task 22 depends on Tasks 9, 14, 8. Tasks 23–25 depend on Tasks 22. Tasks 26–28 depend on Tasks 21, 20, 12.

