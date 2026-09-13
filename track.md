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

## Entry 9 — 2026-09-13: Process standards tightened — doc metadata, PR discipline, pre-commit hooks, gitleaks, husky

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Updated `docs/DEVELOPER_STANDARDS.md`**:
   - Added §3: PR discipline — all claims must be **citation-based** (code location, test output, design doc section, ADR, or reproducible benchmark). False claims are unacceptable.
   - Added §4.1: **Pre-commit testing gate** — unit tests run on `pre-commit`, integration tests on `pre-push`, both enforced by CI. No `--no-verify` for production-bound commits.
   - Added §5: Explicit prohibition of `.env` files, environment variables, and hardcoded secrets in any committed file.
   - Added §6: **Document metadata header standard** — every design doc/spec/plan under `docs/` must begin with `Created:`, `Author:`, `Version:`, `Last Updated:`, `Status:`.
   - Added §7: **Pre-commit toolchain** — required tools (pre-commit, gitleaks, husky, lint-staged), hook stages, setup instructions, skip policy.

2. **Updated `.github/pull_request_template.md`**:
   - Added checkboxes: tests pass locally, no env vars/secrets, citation-based claims, no false claims, doc metadata header present.

3. **Updated `docs/SETUP.md`**:
   - Added §3.1: Pre-commit hooks installation instructions (one-time per clone).

4. **Updated `docs/SECURITY.md`**:
   - Added §2.1: Pre-commit enforcement (gitleaks) — scan rules, remediation steps, `.env.example` as the only allowed env file.

5. **Created `.pre-commit-config.yaml`**:
   - 7 repos/hooks: gitleaks secret scan · ruff lint+format · custom `.env` file scanner · mypy typecheck · pytest unit tests (pre-commit) · pytest integration tests (pre-push) · pnpm lint + typecheck (pre-push).

6. **Created `scripts/pre_commit/no_env_files.py`**:
   - Scans all files for blocked filenames (`.env*`, `*.env`, `.envrc`) and hardcoded secret patterns (GitHub private key, database URL with credentials, KMS master key, AWS secret key, OpenAI API key format).
   - Fails the commit with remediation instructions if violations found.

7. **Updated `package.json`**:
   - Added `"prepare": "husky install"` script.
   - Added `husky` and `lint-staged` to `devDependencies`.

8. **Created `.husky/pre-commit`** and **`.husky/pre-push`**:
   - `pre-commit`: delegates to Python `pre-commit run` + `pnpm format:check` for frontend.
   - `pre-push`: delegates to Python `pre-commit run --hook-stage pre-push` + `pnpm lint` + `pnpm typecheck`.

9. **Updated `docs/specs/2026-09-13-phase1-github-app-webhook-ingestion.md`** (formerly `docs/design/Phase1_GitHubApp_WebhookIngestion_Design.md`):
   - Retroactively added document metadata header per new §6 standard (`Created:`, `Author:`, `Version:`, `Last Updated:`, `Status:`).

### Next

- [ ] Commit + push to `origin/feat/phase1-github-app-webhook-ingestion`
- [ ] Phase 1 build step 1: `packages/config/` (settings, DB engine, Redis client)
- [ ] ADR-006 as implementation progresses

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


---

## Entry 9 — 2026-09-13: Phase 1 design spec enhanced (code quality grilling + brainstorming)

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Pressure-tested the Phase 1 design spec** (`docs/specs/2026-09-13-phase1-github-app-webhook-ingestion.md`) via the grilling + brainstorming skills — 17 design-tree questions across 3 rounds, with web research on webhook error taxonomies (Stripe) and transactional outbox patterns (AWS Prescriptive Guidance).

2. **Updated the Phase 1 spec from v1.0.0 → v1.1.0** with all 17 settled decisions:
   - **Transactional outbox pattern (ADR-006):** eliminated the dual-write hazard (XADD inside DB transaction). `webhook_deliveries` now doubles as the outbox (`enqueued`/`enqueued_at` columns); an outbox publisher coroutine in the worker process polls `WHERE enqueued = false FOR UPDATE SKIP LOCKED`, calls XADD, marks enqueued. Redis is now fully decoupled from the 10-second webhook critical path.
   - **Raw body HMAC (Q1=A):** route handler takes `request: Request`, reads `await request.body()`, verifies HMAC, then parses JSON — no FastAPI auto-parsing on the critical security path.
   - **Thin route handler + explicit transaction (Q5=A):** route delegates to `ingest_webhook()` service function with `async with session.begin()` — no reliance on FastAPI dependency teardown for advisory lock release.
   - **Second idempotency check (Q15=A):** after advisory lock, query `review_runs(pull_request_id, head_sha)` for existing RECEIVED run — prevents duplicate review runs on GitHub redelivery with new delivery_id.
   - **Stripe-style error envelope (ADR-006, Q8=D):** full envelope with `type`, `code`, `param`, `request_id`, `doc_url`; codified webhook error code taxonomy (7 codes). Signature verification returns 401 (GitHub convention, not Stripe's 400).
   - **Trace context propagation (ADR-006, Q9=B):** W3C `traceparent` string in `JobMessage`; OTel inject/extract across Redis Streams process boundary.
   - **Two-layer token cache (Q12=B, Q16=B):** L1 in-memory + L2 Redis shared cache for installation tokens; invalidation propagates via Redis DEL.
   - **Audit sequence via PostgreSQL SEQUENCE (Q14=A):** atomic, non-blocking; gaps on rollback are acceptable (hash-chain integrity is from linking, not contiguity).
   - **Advisory lock key via `hashtextextended` (Q11=A):** 64-bit BIGINT from `repo_id:pr_number:head_sha`.
   - **`payload_size_bytes` column (Q10=B):** monitoring column on `webhook_deliveries` for oversized webhook alerting.
   - **Test plan relabeled (Q2=B):** model tests moved from unit → integration (PostgreSQL required); unit tests are pure (mocked DB/Redis); added `test_outbox_publisher.py`, `test_error_envelope.py`, `test_token_cache.py`, `test_audit_sequence.py`.

3. **Created 1 consolidated ADR** (`docs/adr/adr-006-phase1-github-app-webhook-ingestion.md`) — covers all Phase 1 architectural decisions (outbox, priority streams, schema, adapter, worker, error envelope, trace propagation) in a single per-phase ADR.

4. **Updated `docs/adr/README.md`** index — added ADR-006 entry.

5. **Updated `docs/CODE_STANDARDS.md §3`** — error envelope changed from `{code, message, details}` to Stripe-style `{type, code, message, param, request_id, doc_url}` per ADR-006.

6. **Reorganized spec storage** — moved the spec from `docs/design/Phase1_GitHubApp_WebhookIngestion_Design.md` to `docs/specs/2026-09-13-phase1-github-app-webhook-ingestion.md` (new `docs/specs/` folder; naming convention: `YYYY-MM-DD-<feature>.md`).

### Next

- [ ] Commit + push to `origin/feat/phase1-github-app-webhook-ingestion`
- [ ] Phase 1 build step 1: `packages/config/` (settings, DB engine, Redis client)
- [ ] Implement ADR-006 as code lands


---

## Entry 10 — 2026-09-13: Phase 1 implementation plan created

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Created `docs/implementation-plans/` folder** — new folder for executable build plans, alongside existing `docs/specs/` and `docs/adr/`.

2. **Wrote implementation plan** (`docs/implementation-plans/2026-09-13-phase1-github-app-webhook-ingestion.md`) — a detailed, milestone-by-milestone decomposition of the Phase 1 spec into 10 committable units (M1–M10):
   - Each milestone lists: purpose, files to create (with key functions/schemas), acceptance criteria, and suggested Conventional Commit message.
   - Dependency order: M1 (config) → M2 (models) → M3 (migrations) → (M4 ∥ M5) → M6 (GitHub adapter) → M7 (orchestration) → M8 (FastAPI app) → M9 (worker) → M10 (tests).
   - Includes full testing strategy (unit → integration → e2e), Definition of Done checklist, Risks & Mitigations table, and deferred-scope reference.
   - Notes prerequisite items already done (ADR-006, CODE_STANDARDS §3, spec in `docs/specs/`).

### Next

- [ ] Commit + push to `origin/feat/phase1-github-app-webhook-ingestion`
- [ ] Phase 1 build step 1: `packages/config/` (settings, DB engine, Redis client)
- [ ] Continue through build order steps 2–13 per spec §14 / implementation plan M1–M10



---

## Entry 11 — 2026-09-13: Phase 1 implementation plan rewritten in writing-plans skill format

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Deleted the ad-hoc implementation plan** (`docs/implementation-plans/2026-09-13-phase1-github-app-webhook-ingestion.md` v1.0.0) that was written without the `writing-plans` skill and lacked executable TDD steps.

2. **Recreated the plan using the `writing-plans` skill** — the new plan follows the required format exactly:
   - **Required header:** `> For agentic workers:` directive with sub-skill reference (subagent-driven-development / executing-plans), Goal, Architecture, Tech Stack, Global Constraints, Source Documents, File Structure.
   - **29 tasks**, each with: Files (Create/Modify/Test with exact paths), Interfaces (Consumes/Produces), and 5 TDD steps (write failing test with real code → run to see FAIL → write implementation with real code → run to see PASS → Conventional Commit).
   - **Real, runnable code** in every step — no placeholders. Tests, implementations, migration SQL, and shell commands are all complete and executable by a zero-context engineer/subagent.
   - **Interface contracts** (Consumes/Produces) on every task so subagents know exactly what each module provides and depends on.
   - **Exact commands with expected output** — every test step specifies the `pytest` invocation and the expected FAIL/PASS result.
   - **Self-review pass** — a completed checklist verifying all skill requirements are met, plus 5 explicitly documented scope decisions/gaps.
   - **Definition of Done** checklist (12 items: tests, lint, mypy, coverage ≥80%, migration, e2e, endpoint behavior, no credentials).
   - **Risks & Mitigations** table (5 risks with likelihood/impact/mitigation).
   - **Execution Notes** — parallelizable task groups and sequential dependency chains for subagent dispatch.

3. **Task decomposition** (10 milestones → 29 TDD tasks):
   - M1 config (Tasks 1–3): settings, DB engine, Redis client + stream constants
   - M2 models (Tasks 4–9): base+enums, identity tables, repository tables, review tables, audit+webhook_deliveries, Pydantic schemas
   - M3 migration (Task 10): Alembic setup + initial 14-table schema with indexes + audit sequence
   - M4 observability (Tasks 11–12): structlog setup + traceparent inject/extract
   - M5 security (Tasks 13–14): HMAC-SHA256 verify + advisory lock
   - M6 GitHub adapter (Tasks 15–19): error hierarchy, JWT generation, token cache, webhook event filter, API client
   - M7 orchestration (Tasks 20–22): producer, consumer, ingest_webhook service
   - M8 API (Tasks 23–25): app factory+lifespan+deps, health router, webhooks router+error envelope
   - M9 worker (Tasks 26–28): main+consumer loop, outbox publisher, janitor
   - M10 tests (Task 29): fixtures + e2e pipeline test

### Next

- [ ] Commit + push the rewritten plan to `origin/feat/phase1-github-app-webhook-ingestion`
- [ ] Begin M1 implementation (Task 1: `packages/config/settings.py`) using subagent-driven-development

