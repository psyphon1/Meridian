# Meridian — Local Development Setup

**Targets: Python 3.12+, Node 20+ LTS, pnpm, Docker Desktop, GitHub CLI (`gh`), PostgreSQL 16, Redis 7.** 12-factor rule: all environment-varying config lives in `.env` (never committed), code contains no credentials.

---

## 1. One-Time Bootstrap

```powershell
git clone https://github.com/psyphon1/Meridian.git
cd Meridian
cp .env.example .env            # fill in real values
gh auth switch -u psyphon1      # or your own account
.\scripts\bootstrap\bootstrap.ps1   # or: make bootstrap (once Makefile is filled)
```

`bootstrap` should: create Python venv (`pyproject.toml`-driven install), `pnpm install` (workspace via `pnpm-workspace.yaml`), start Postgres/Redis via `docker-compose.yml`, and apply `db/migrations/`.

## 2. Required Credentials (local dev)

| Credential | Source | Env var (see `.env.example`) |
|---|---|---|
| GitHub App | Create a dev App at `https://github.com/settings/apps/new` (minimum permissions, pull_request + installation webhooks) | `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET` |
| OAuth App | GitHub settings → OAuth Apps (callback `http://localhost:3000/api/auth/callback`) | `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` |
| LLM key | Any LiteLLM-supported provider | provided per-user in the dashboard, not in `.env` for app code |
| Postgres / Redis | docker-compose defaults | `DATABASE_URL`, `REDIS_URL` |
| KMS | Local dev: env-based master key | `KMS_MASTER_KEY` |

**Webhook forwarding:** use `gh webhook forward` (or smee) to route GitHub deliveries to `http://localhost:8000/webhooks/github` during development.

## 3. Daily Workflow

```powershell
docker compose up -d postgres redis   # start dependencies
make dev                              # api + worker + web (once Makefile is filled)
pytest                                # tests/ (unit → integration → e2e)
```

- API: http://localhost:8000 (OpenAPI at `/docs`) · Web: http://localhost:3000
- Workers need at least one running worker process to drain Redis Streams consumer groups.

## 4. Conventions

- Python: `ruff` + `mypy` strict (see CODE_STANDARDS.md); TypeScript: `tsc --strict` + `eslint` + `prettier`.
- DB schema changes only via `db/migrations/` (never edit `db/schema/` by hand) — see ADR-006 rule in DEPLOYMENT.md on backward-compatible migrations.
- Prompts live in `prompts/` — version-controlled, never inline in code.
- Never commit `.env`; the repo's litmus test is that it could be made public without leaking credentials (12-factor).

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Webhooks not arriving locally | `gh webhook forward` still running? Signature check failing → `GITHUB_WEBHOOK_SECRET` mismatch |
| `QUEUED_NO_KEY` stuck | Add a BYOK key in the dashboard for the tenant |
| Worker not consuming | Check consumer group exists; janitor `XAUTOCLAIM` may have claimed your stalled entries — check attempt counters |
| Migration drift | Reset dev DB from `db/seeds/`; never hand-edit `alembic_version` |
