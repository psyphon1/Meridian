# Meridian — Autonomous AI PR Reviewer
# Code Standards

**Per v2 spec §41 and the design doc's engineering standards.**

> **AI agents:** [`AGENTS.md`](../AGENTS.md) at the repo root is your entry point — you MUST follow these code standards for every line of code you write, and follow all design docs in [`design/`](design/). See also [`DEVELOPER_STANDARDS.md`](DEVELOPER_STANDARDS.md) for workflow rules.

## 1. Python (API, worker, services, packages)

### 1.1 Hard rules (non-negotiable)

1. **Type hints everywhere.** All public functions, class methods, and module-level constants are fully annotated. `mypy` in **strict mode** (`pyproject.toml`) runs in CI; no new `# type: ignore` without a comment explaining why.
2. **No bare `except:`** — ever. Catch specific exception types; the narrowest type that makes semantic sense.
3. **PEP 8 formatting via Ruff.** Line length 100. Import order enforced (`I` rule): stdlib → third-party → first-party, blank-line separated. Ruff runs as both linter and formatter.
4. **Explicit exception hierarchy.** Custom exceptions live in a package-level `errors.py` and subclass a shared base (`MeridianError`). Never raise bare `Exception` or `ValueError` for domain conditions — define purpose-built types.
5. **No business logic in routes/controllers.** Handlers validate + delegate only. Orchestration is in services/packages. See `docs/PROJECT_STRUCTURE.md` dependency rules.

### 1.2 Tooling (configured in `pyproject.toml`)

| Tool | Purpose | Invocation |
|---|---|---|
| Ruff | Lint + format | `ruff check .` / `ruff format .` (or `make lint`) |
| mypy | Type-check domain contracts | `mypy apps packages services` (or `make typecheck`) |
| pytest | Tests | `pytest` (or `make test`) |
| pre-commit | Local gate before push | `pre-commit install` |

### 1.3 Naming

- Modules/packages: `snake_case` (no dashes, no camelCase).
- Classes: `PascalCase`. Functions/variables: `snake_case`. Constants: `UPPER_SNAKE_CASE`.
- Private module members prefix with single underscore (`_helper`). Avoid `__dunder` names may conflict with Python internals.
- Pydantic models: field names match the DB/JSON contract; use `alias` only when the wire format differs.

### 1.4 Async & concurrency

- The webhook gateway and workers are async-first (`FastAPI`, `httpx`, `redis.asyncio`). Use `async`/`await` in I/O paths; don't block the event loop with sync DB or network calls.
- Shared mutable state across coroutines requires an explicit lock or an actor model — never assume atomicity.

## 2. TypeScript (web dashboard)

1. **Strict mode** TypeScript (`strict: true`, plus `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`). No `any` — use `unknown` + narrowing, or precise generics.
2. **ESLint + Prettier.** Same import ordering discipline as Python; no unused vars/imports; exhaustive dependency arrays in React hooks.
3. **React component conventions.** Function components + hooks only; `props` interfaces named `*Props`; business logic extracted to `packages/`/`apps/web/src/lib`, never embedded in JSX.
4. **Component/unit tests** for UI behavior — every interactive state (loading, empty, error, success, escalated) has a tested path. RTL (`@testing-library/react`) preferred over implementation-detail assertions.
5. **Accessibility.** Semantic HTML, keyboard navigable, aria-labels on icon-only controls. See [`docs/UI_UX.md`](UI_UX.md).

## 3. API

- **OpenAPI contract** auto-generated from FastAPI + Pydantic; every endpoint has a versioned path (`/v1/...`), request/response models, and documented errors.
- **Consistent error envelope** (Stripe-style, per ADR-006): `{ "error": { "type": "...", "code": "...", "message": "...", "param": "...", "request_id": "...", "doc_url": "..." } }`. `type` is the broad category (`webhook`, `auth`, `rate_limit`, `validation`, `internal`); `code` is the specific machine-readable string (namespaced, e.g., `webhook.signature_invalid`); `param` identifies the offending input (`null` when not applicable); `request_id` correlates to OTel trace ID; `doc_url` links to error docs (`null` until docs exist). No secrets, stack traces, or internal identifiers in error responses.
- **Versioning:** breaking changes -> new minor version (e.g. `/v2/...`); the old version stays available for at least one release cycle with a deprecation header.

## 4. Git

- Protected `main`; all changes via PR with CI passing.
- **Conventional Commits** only: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `build:`, `perf:`, `security:`, `revert:`. Scope optional: `feat(api): ...`.
- `CODEOWNERS` enforcement — every path resolves to a maintainer before merge.
- One logical change per PR (see `docs/DEVELOPER_STANDARDS.md` for size limits).

## 5. Security tooling in CI

Dependency scanning · secret scanning (gitleaks) · SAST (CodeQL + Semgrep) · SBOM generation (anchore/syft). All wired in `.github/workflows/ci.yml`. No credentials in source, images, or logs — ever.

## 6. Testing rule

- Behavior changes include tests. Production bugs get regression tests where practical.
- Test quadrants: **unit** (no I/O) → **integration** (backing services via docker-compose) → **security** (evidence-gate + sandbox) → **e2e** (full pipeline). See `docs/DEVELOPER_STANDARDS.md`.
- Coverage tracked via `pytest-cov`; contract-critical packages aim for ≥ 80% branch coverage.
