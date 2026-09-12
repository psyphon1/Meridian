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

---

## Entry 3 — 2026-09-12: AGENTS.md agent entry point

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Created root `AGENTS.md`** — mandatory entry point for all AI coding agents working on this repo:
   - Non-negotiable reading order: AGENTS.md → all design artifacts in `docs/design/` (Design_Doc_Final.html = source of truth) → `docs/CODE_STANDARDS.md` → `docs/DEVELOPER_STANDARDS.md` → task-relevant docs
   - Hard rules: follow all `docs/design/` docs, always follow CODE_STANDARDS + DEVELOPER_STANDARDS, ADR before architecture changes, dependency rules, evidence gate is non-bypassable, trust hierarchy absolute, update track.md
   - Working conventions + conflict-precedence chain
2. **Wired agent compliance notes into every standards doc**: `CODE_STANDARDS.md`, `DEVELOPER_STANDARDS.md`, `AGENT_STANDARDS.md` (scope note: product LLM agents vs coding agents), `SECURITY.md`, `COMPLIANCE.md`, `PROJECT_STRUCTURE.md`, `UI_UX.md` — each points to `AGENTS.md` as the entry point.
3. **Linked AGENTS.md** from `README.md` (Documentation section) and `docs/README.md` index.

### Pending from Entry 2

- [ ] Push to `origin/main` (was interrupted by credential-helper fix; GCM stale account resolved)



---

## Entry 4 — 2026-09-12: Scaffold full project structure

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. Added `.gitkeep` placeholders to all 54 empty directories matching `docs/design/Meridian_PROJECT_STRUCTURE.md` §1: `apps/{api,worker,web,github-app}`, `packages/*` (13), `services/*` (5), `infra/{terraform/{modules,environments/{dev,staging,production}},kubernetes/{base,overlays},docker,sandbox}`, `db/{migrations,seeds,schema}`, `prompts/*` (4), `evals/*` (5), `tests/*` (5), `scripts/*` (5), `.github/{workflows,ISSUE_TEMPLATE}`.
2. Committed as `chore: scaffold full monorepo project structure with .gitkeep placeholders` and pushed to `origin/main`.

### Notes

- Root scaffold files (`Makefile`, `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `docker-compose.yml`) exist and are tracked, intentionally empty pending Phase 1.
- Git doesn't track empty directories — `.gitkeep` files make the skeleton visible on GitHub; remove each as real content lands.
---

## Entry 5 — 2026-09-13: Production-ready config + docs rebrand/expansion

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Filled the previously-empty build/config files** with real, working content:
   - `pyproject.toml` — Python 3.12+ project (FastAPI, LangGraph, LiteLLM, SQLAlchemy+psycopg, pgvector, Redis, structlog, OpenTelemetry) with Ruff/mypy/pytest tooling, version 0.1.0.
   - `package.json` + `pnpm-workspace.yaml` — pnpm@9 workspace, Node 20+, strict TypeScript, ESLint + Prettier.
   - `docker-compose.yml` — Postgres 16 (pgvector) + Redis 7 backing services.
   - `Makefile` — developer task runner (lint, typecheck, test, dev, bootstrap).
2. **CI pipeline** created at `.github/workflows/ci.yml`: Python (Ruff → mypy → pytest), frontend (ESLint + tsc), Gitleaks secret scan, CodeQL SAST, anchore/syft SBOM.
3. **Repo hygiene**: `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/bug_report.yml` + `feature_request.yml`, expanded `.env.example` (OAuth vars, model ceiling, sandbox limits), commented `.dockerignore`, `scripts/bootstrap/bootstrap.ps1`, `tests/test_smoke.py`.
4. **Env-var drift reconciled**: `.env.example` and `docs/SETUP.md` now document `KMS_MASTER_KEY` (local KEK) **and** `SECRET_MANAGER_ENDPOINT` (Vault/cloud KMS) as complementary, with precedence clarified — neither dropped.
5. **New brand positioning applied** repo-wide — "**Meridian — Autonomous AI PR Reviewer**" + tagline "**Your autonomous first-pass senior engineer for every GitHub pull request**" — to `README.md`, `AGENTS.md`, all `docs/` working docs, and all `docs/design/` artifacts (including `Meridian_Design_Doc_Final.html` title/meta/H1/appendix).
6. **Version numbers unified → 2.1** across `PRD.md`, `SDD.md`, `TRD.md`, and the design `SDD`/`TRD`/`Architecture` docs + the HTML appendix.
7. **Thin docs expanded with concrete, numbered requirements, tables and examples**: `CODE_STANDARDS.md` (hard rules, tooling matrix, naming, async), `DEVELOPER_STANDARDS.md` (DoD checklist, PR size limits, testing quadrants), `AGENT_STANDARDS.md` (output schema, evaluation gating), `PRD.md` (FR table with acceptance criteria, success-metrics table, expanded goals/user-stories/non-goals).
8. **Single-source-of-truth note** added to `docs/README.md`, explicitly resolving the `docs/` vs `docs/design/` layering (design docs are authoritative; update both on contract changes).

### Next

- [ ] Commit + push to `origin/main` as psyphon1
- [ ] Phase 1 build: GitHub App + OAuth + FastAPI + PostgreSQL + Redis Streams + basic review publishing
- [ ] ADR-006+ as architecture decisions are made

---

## Entry 6 — 2026-09-13: Production-ready scaffold pushed + beginner's guide

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Committed and pushed** the full production-ready scaffold to `origin/main` as `58dd5c7` — `chore(repo): production-ready scaffold — config, CI, docs rebrand & expansion` (37 files, +1,020 / −114), closing Entry 5's "Next" item.
2. **Smoke tests validated** — `tests/test_smoke.py` passes (4/4) under Python 3.12; `package.json` parses; `pyproject.toml` / CI workflow verified present and well-formed.
3. **Final drift scan clean** — zero remaining `Production-Grade AI PR Reviewer`, `Version: 2.0`, or stale positioning strings anywhere in the repo; fixed the one leftover tagline variant in `docs/design/Meridian_Full_Session_Context.md`.
4. **Added `docs/BEGINNERS_GUIDE.md`** — a no-prerequisite, plain-English overview covering the one-sentence idea, the problem, the 10-step pipeline, the evidence gate, the tech stack, ADRs, security (BYOK/trust-hierarchy/sandbox/isolation), repo layout, roadmap, user journey, success metrics, and V1 non-goals.
5. **Linked the guide from `docs/README.md`** in the documentation index (first row).

### Next

- [ ] Phase 1 build: GitHub App + OAuth + FastAPI + PostgreSQL + Redis Streams + basic review publishing
- [ ] ADR-006+ as architecture decisions are made

---

## Entry 7 — 2026-09-13: Complete learning guide (tech stack + system design + scaling)

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Created `docs/LEARNING_GUIDE.md`** — a comprehensive 3,350-line, 51-section learning curriculum structured as complete course notes. Organized into five parts:
   - **Part I — Foundations** (sections 1-6): pull requests, APIs (REST/webhooks/async), databases, queues, microservices, system-design thinking framework.
   - **Part II — Technology Stack** (sections 7-25): every tool Meridian uses — Python 3.12+, FastAPI, Pydantic, SQLAlchemy + Alembic, PostgreSQL + pgvector, Redis + Redis Streams, LangGraph, LiteLLM, tree-sitter + SCIP/LSP, Semgrep + CodeQL, Firecracker/gVisor, KMS/Vault, OpenTelemetry + Langfuse, structlog, Next.js + TypeScript, Docker, Kubernetes, Terraform, GitHub App + Webhooks. Each section follows the **What / Why / How / Syntax / Example / System-design takeaway** structure.
   - **Part III — System Design Deep Dive** (sections 26-38): event-driven architecture, pipeline pattern, queue design at production scale, the evidence gate (core safety mechanism), trust hierarchy and prompt injection defense, tenant isolation, BYOK + envelope encryption, risk-adaptive compute, hash-chained audit log, circuit breakers/rate limiting/backoff, checkpointing and resumable workflows, the C4 model, modular monorepo boundaries.
   - **Part IV — Scaling Meridian** (sections 39-47): horizontal vs. vertical scaling, database scaling (partitioning/read replicas/pooling), queue scaling (consumer groups/priority lanes), caching strategy, sandbox pool management, LLM cost control (token budgets/per-tenant ceilings), observability at scale (golden signals/SLOs/error budgets), deployment strategy (canary/blue-green), failure modes and mitigations (chaos engineering).
   - **Part V — Complete Project Walkthrough** (sections 48-51): full architecture diagram, a timestamped end-to-end walkthrough of a real PR review (T+0s through T+43s), ADRs explained with ADR-004 as a full example, how to read and navigate the codebase, local setup commands, and a conclusion with the five most important principles.
2. **Linked the guide from `docs/README.md`** in the documentation index (second row, after the beginner's guide).
3. Built the document in ~30 editor chunks due to the 6,000-character new_text limit per call — all sections verified present and well-formed.

### Next

- [ ] Commit + push to `origin/main`
- [ ] Phase 1 build: GitHub App + OAuth + FastAPI + PostgreSQL + Redis Streams + basic review publishing
- [ ] ADR-006+ as architecture decisions are made

---

## Entry 8 — 2026-09-13: Root README expanded to industry-standard project README

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Rewrote `README.md`** from a ~43-line stub into a complete, industry-standard open-source project README (244 lines), drawing every fact from the authoritative docs (PRD, SDD, TRD, ARCHITECTURE, PROJECT_STRUCTURE, SETUP, SECURITY, OBSERVABILITY, COMPLIANCE) and the root build config (`pyproject.toml`, `package.json`, `docker-compose.yml`, `Makefile`).
2. **Sections added** (in standard open-source order): shields.io badges (CI/license/Python/Node/TypeScript/status/Conventional Commits) · pitch · problem statement · feature list · 10-stage pipeline · six core design principles · tech-stack table (16 layers with roles) · repository structure + dependency rules · getting started (honest about Pre-Alpha state) · documentation index table (17 docs) · ADR table · status & roadmap (P1–P9) · success metrics · security summary · contributing conventions · license.
3. Kept the README **accurate to repo status**: flagged Pre-Alpha, noted which commands work today (backing services, smoke tests) vs. which land with Phase 1 code (`make dev` / app services).

### Next

- [ ] Commit + push to `origin/main`
- [ ] Phase 1 build: GitHub App + OAuth + FastAPI + PostgreSQL + Redis Streams + basic review publishing
- [ ] ADR-006+ as architecture decisions are made


