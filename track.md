# Meridian — Work Track

> Running log of everything done on the Meridian project. Newest entries last.

---

## Entry 1 — 2026-09-12: Project bootstrap

**Performed by:** Cofounder session (agent) with Chinmay Duse (psyphon1)

### Done

1. **Repo initialized** — `git init` in `d:\og\Meridian`, default branch renamed `main`.
2. **Git identity (local to this repo)** — `user.name = psyphon1`, `user.email = psyphon1@users.noreply.github.com`.
3. **GitHub CLI** — switched active `gh` account to **psyphon1** (`gh auth switch -u psyphon1`). Was previously `akshada-londhe`.
4. **Remote connected** — `origin = https://github.com/psyphon1/Meridian.git`.
5. **Directory structure created** — full skeleton per `Meridian_PROJECT_STRUCTURE.md`:
   - `apps/` → api, worker, web, github-app
   - `packages/` → agents, orchestration, code-intelligence, retrieval, evidence, analyzers, sandbox, github, risk-engine, models, security, observability, config
   - `services/` → repository-indexer, review-engine, evidence-engine, notification-service, audit-service
   - `infra/` → terraform (modules + dev/staging/production envs), kubernetes (base + overlays), docker, sandbox
   - `db/` → migrations, seeds, schema
   - `docs/` (+ `docs/adr/`), `prompts/` (system, review, evidence, adjudication), `evals/` (datasets, cases, graders, regression, reports), `tests/` (unit, integration, security, e2e, fixtures), `scripts/` (bootstrap, indexing, evaluation, migrations, development), `.github/` (workflows, ISSUE_TEMPLATE)
6. **Root files created** — `.gitignore`, `README.md`, `LICENSE`, `.dockerignore`, `.env.example`, `Makefile`, `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `docker-compose.yml`.
   - Build/config files (`Makefile`, `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `docker-compose.yml`) are created **empty on purpose** — no code filling in this step per decision.
7. **Docs filled with industry-standard content** (based on web research of standards):
   - `docs/README.md` (index), `docs/PRD.md`, `docs/SDD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STRUCTURE.md`
   - `docs/SECURITY.md` (SANS policy structure + OWASP ASVS), `docs/COMPLIANCE.md`
   - `docs/CODE_STANDARDS.md`, `docs/DEVELOPER_STANDARDS.md`, `docs/AGENT_STANDARDS.md`
   - `docs/UI_UX.md`, `docs/SETUP.md`, `docs/DEPLOYMENT.md` (12-factor config via env, CircleCI best practices), `docs/OBSERVABILITY.md` (4 golden signals, traces/metrics/logs)
   - `docs/adr/README.md` (ADR process, based on Michael Nygard / MADR format) + ADR-001…ADR-005 from the design doc
   - `.github/pull_request_template.md`, `.github/dependabot.yml`
8. **No `.gitkeep` files used** — per owner decision, root `.gitignore` only.

### Industry-standard sources used

- PRD: Atlassian PRD template, ClickUp PRD guide, GeeksforGeeks PRD structure
- Architecture/SDD: Arc42, C4 model (arcdri.cwi.nl), GeeksforGeeks SDD
- ADRs: Michael Nygard format, MADR (adr.github.io), GitLab ADR docs
- Security: SANS information-security policy templates, OWASP ASVS
- CI/CD: CircleCI best-practices blog
- Observability: Grafana "4 golden signals" (Google SRE)

### Not done yet (next steps)

- [ ] Commit + push to `origin/main`
- [ ] Fill `Makefile`, `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `docker-compose.yml` (when code phase starts)
- [ ] Phase 1 build order: GitHub App + OAuth + FastAPI + PostgreSQL + Redis Streams + basic review publishing
- [ ] CI workflow files under `.github/workflows/`
- [ ] ADR-006+ as decisions are made

---

## Entry 2 — 2026-09-12: Deep research pass on docs + file moves

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Full web research** (live fetches, not just snippets):
   - GitHub App best practices (docs.github.com) — minimum permissions, rate-limit handling, token caching/expiry, credential breach plan, security logging, data deletion
   - Webhook best practices (docs.github.com) — 10-second response window, HMAC secret verification, `X-GitHub-Delivery` idempotency/replay defense, event+action filtering, IP allowlisting (`GET /meta`), missed-delivery redelivery
   - 12-Factor App (Config) — config/code separation, granular orthogonal env vars
   - Google SRE Book Ch. 6 — four golden signals, symptom-based paging, percentile measurement
   - OWASP Top 10 for LLM Applications — all 10 risks mapped to Meridian controls
   - OWASP ASVS — levels, `v<version>-<chapter>.<section>.<requirement>` ID format, target Level 2
   - ADR/MADR (adr.github.io) — Nygard + MADR template structure, decision-log practice
   - ProductPlan PRD guide — release completeness practice ("if it isn't in the PRD, it won't ship")
   - Martin Fowler — Blue-Green deployment, schema-migration decoupling from app upgrades
2. **Moved root design artifacts → `docs/design/`**: `Meridian_Architecture.md`, `Meridian_SDD.md`, `Meridian_TRD.md`, `Meridian_PROJECT_STRUCTURE.md`, `Meridian_Design_Doc_Final.html`, `Meridian_Full_Session_Context.md`.
3. **Updated cross-references** in `docs/README.md`, `ARCHITECTURE.md`, `PROJECT_STRUCTURE.md`, `SDD.md`, `TRD.md`.
4. **Enriched existing docs:**
   - `PRD.md` — Release Criteria (launch gate), Assumptions & Dependencies
   - `ARCHITECTURE.md` — Webhook Ingestion Contract (10s window, replay defense, IP allowlist, permission re-approval) + GitHub App credential lifecycle
   - `SDD.md` — Queue Design (Redis Streams at-least-once, PEL, `XAUTOCLAIM` janitor, dead-letter) + GitHub Integration Contract table
   - `SECURITY.md` — ASVS v5.0.0 Level 2 target with ID format, full OWASP LLM Top 10 → control mapping table, credential breach response playbook
   - `TRD.md` — SLO frame per golden signals (SLI/SLO table, error budget)
5. **Created missing docs:**
   - `docs/SETUP.md` (bootstrap, credentials, webhook forwarding, troubleshooting)
   - `docs/DEPLOYMENT.md` (12-factor, environments, blue-green with migration decoupling, release checklist, rollback)
   - `docs/OBSERVABILITY.md` (golden signals, alert policy page/ticket/dashboard, tracing with Langfuse redaction, dashboards)
   - `docs/adr/README.md` (MADR process) + `template.md` + ADR-001…ADR-005 (full context/drivers/options/decision/consequences)
   - `.github/pull_request_template.md` (Conventional Commits + project-specific checklist)
   - `.github/dependabot.yml` (pip + npm + github-actions + docker, weekly, grouped)

### Next

- [ ] Commit + push to `origin/main` as psyphon1
- [ ] Fill `Makefile`, `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `docker-compose.yml` (code phase)
- [ ] Phase 1 build order: GitHub App + FastAPI + PostgreSQL + Redis Streams + basic review publishing
- [ ] CI workflow files under `.github/workflows/`
