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

---

## Entry 12 — 2026-09-13: Phase 1 build M1–M3 (config + models + Alembic migration) in stacked worktrees

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Docs committed on main** (`71f3574`): Phase‑1 spec, ADR‑006, implementation plan v2, CODE_STANDARDS, track.md. (Removed a stale `.git/index.lock` that blocked an earlier commit.)
2. **Config worktree — M1 complete** (`feature/config` @ `f9603a7`): typed `pydantic-settings` (`Settings`), async engine + session factory (`packages/config/database.py`), async Redis client + stream constants (`packages/config/redis.py`). 7/7 unit tests pass. Added root `conftest.py` (sys.path bootstrap). Added `packages/__init__.py` so mypy resolves `packages.*` under a single module name (fixed "Source file found twice" error). mypy strict clean; ruff clean.
3. **Models worktree — M2 + M3 complete** (`feature/models` @ `2206f8f`, 3 commits):
   - `feat(models): declarative base, domain enums, 12 table models, pydantic schemas` — `base.py` (DeclarativeBase, `TimestampMixin`, `CreatedAtMixin`, enums `ReviewStatus`/`RiskTier`/`FindingSeverity`/`InstallationStatus`/`PRState`), `identity.py` (User, APIKey, Installation), `repository.py` (Repository, Commit, File, CodeSymbol), `review.py` (PullRequest, ReviewRun, Evidence, Finding, ToolRun, ReviewMemory), `audit.py` (AuditEvent hash-chained, WebhookDelivery outbox), `schemas.py` (JobMessage, IngestResult, WebhookHeaders, PR/Installation payloads).
   - `style(models)`: ruff format + import sorting + line-length fixes.
   - `feat(models): alembic migration 001 + ephemeral db/redis test fixtures` — `db/migrations/` (alembic.ini, async `env.py` reading `MERIDIAN_DATABASE_URL` via `packages.config.settings`, script.py.mako, `001_initial_schema.py` with all 14 tables + 8 indexes + `audit_events_seq` + full downgrade), `tests/fixtures/db.py` (ephemeral per-session Postgres DB, skips when unreachable, `connect_timeout=3`), `tests/fixtures/redis.py` (DB 15, flushed), integration test `test_migration_001.py` driving Alembic via API.
4. **Test/lint results (models worktree):** ruff check ✓, ruff format ✓, mypy --strict on `packages/models` ✓ (7 files), **36/36 unit tests pass**; integration test skips cleanly without backing services (Windows: `WindowsSelectorEventLoopPolicy` set in root conftest for psycopg async).
5. **Branch stack re-aligned** after amending `feature/config`: `feature/config` → `feature/models` → `feature/obs_sec` → `feature/github_orch` → `feature/api` → `feature/worker` (obs_sec/github_orch/api/worker currently empty branches at the models tip).

### Lessons / gotchas

- mypy needs `packages/__init__.py` (regular package) or it sees files under two module names (`models.base` vs `packages.models.base`).
- Adding `packages/__init__.py` flips ruff isort's first-party detection — `packages.*` imports move to a separate section (auto-fixed).
- `git rebase` of stacked worktrees after amending the base commit: old base commit replays as a conflict → `git rebase --skip` takes the amended version; empty downstream branches need an explicit `git reset --hard <upstream>` (plain rebase reports "up to date" without moving them).
- psycopg async on Windows requires SelectorEventLoop — set in root `conftest.py`.

### Next

- [x] M4/M5: implement Tasks 11–14 (observability + security) in the obs_sec worktree — `feature/obs_sec` @ `46e6b97` (4 commits: structlog setup `7fae653`, traceparent inject/extract `38f92d4`, HMAC-SHA256 verify `23a6b1d`, advisory lock `46e6b97`). ruff ✓, mypy --strict ✓, **47/47 unit tests pass**. Downstream empty branches (github_orch, api, worker) re-pointed to `46e6b97`.
- [x] M6+: github_orch → api → worker worktrees in stack order
- [x] Open PRs (owner-approved 2026-09-13) — stacked series opened: **PR #1** `feature/config` → `main`, **PR #2** `feature/models` → `feature/config`, **PR #3** `feature/obs_sec` → `feature/models` (github_orch/api/worker are empty — no PRs until they have commits). Branches pushed; `main` (docs) pushed first to give PR #1 a clean base.
- [ ] Optionally `docker compose up -d postgres redis` to exercise the integration test end-to-end

---

## Entry 13 — 2026-09-13: Phase 1 build M6 (Tasks 15–19, GitHub adapter) in the github_orch worktree

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **GitHub adapter complete** (`feature/github_orch`, 5 sequential TDD commits, one per task, per the plan's commit steps):
   - `feat(github): error hierarchy matching HTTP status codes` (`db49a33`) — `packages/github/errors.py`: `MeridianError` → `GitHubError` → `AuthenticationError` (401) / `RateLimitError` (429/403, carries `retry_after`) / `NotFoundError` (404) / `ValidationError` (422) / `ServerError` (5xx). Package `__init__.py` + `py.typed`.
   - `feat(github): RS256 App JWT generation with 10-min expiry` (`4c0cb44`) — `packages/github/auth.py`: `generate_app_jwt(private_key, app_id)` via PyJWT, `iat` −60s clock-skew tolerance, `exp` = iat + 660.
   - `feat(github): two-layer installation token cache (L1 in-memory + L2 Redis)` (`b88c551`) — `packages/github/token_cache.py`: `InstallationTokenCache.get_token` (L1 → L2 → GitHub fetch, writing both layers with TTL = expiry − 60s) and `invalidate`; injectable `fetch_token` for testing.
   - `feat(github): allowed events/actions filter for webhook ingestion` (`f0031ab`) — `packages/github/webhooks.py`: `ALLOWED_EVENTS` (`pull_request`: opened/synchronize/reopened/edited; `installation`: created/deleted/new_permissions_accepted; `installation_repositories`: added/removed) + `is_event_allowed`.
   - `feat(github): typed async API client with rate-limit error mapping` (`a6ae479`) — `packages/github/client.py`: `GitHubClient` with `get_pr_files` / `get_pr_diff` / `post_review` / `post_comment` over `httpx.AsyncClient`; `_check_response` maps status codes onto the Task-15 error hierarchy (reads `Retry-After` on 429/403).
2. **Test/lint results (github_orch worktree):** ruff check ✅, ruff format ✅, mypy --strict on `packages/github` ✅ (6 files), **62/62 unit tests pass** (15 new: errors 3, auth 2, token cache 2, webhooks 6, client 2).
3. TDD followed per task: failing test → minimal implementation → green. Not yet pushed (stack: PR #1–#3 must merge first; `feature/github_orch` sits on `feature/obs_sec`).

### Lessons / gotchas

- Running `ruff check --fix` before finishing an edit batch can strip imports that are *about to be used* (it removed `Any` from `client.py` mid-refactor) — re-run the full gate after each edit batch.
- Ruff S105 flags fake token literals in tests (`"token-abc"`, `"mock.jwt.token"`) — suppressed with `# noqa: S105` since they are test fixtures, not secrets.
- `InstallationTokenCache.get_token` L2 hit: Redis `get` returns `Any` → wrap with `str(...)` to keep mypy `--strict` (`no-any-return`) clean; client `resp.json()` wrapped in `cast(list[dict[str, Any]], ...)`.

### Next

- [ ] Await review/merge of PR #1 → #2 → #3, then open PRs for `github_orch` (and downstream) and push `feature/github_orch`.
- [ ] M7 (Tasks 20–22, orchestration producer/consumer) in the `github_orch` worktree, continuing the stack.
- [ ] Then `api` (M8) and `worker` (M9–M10) milestones.

- [ ] Await review/merge of PR #1 → #2 → #3, then open PRs for `github_orch` (and downstream) and push `feature/github_orch`.
- [ ] M7 (Tasks 20–22, orchestration producer/consumer) in the `github_orch` worktree, continuing the stack.
- [ ] Then `api` (M8) and `worker` (M9–M10) milestones.

---

## Entry 14 — 2026-09-13: Phase 1 build M7 (Tasks 20–22, orchestration) in the github_orch worktree

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Orchestration package complete** (`feature/github_orch`, 3 TDD commits + 1 chore, per the plan's commit steps):
   - `feat(orchestration): Redis Streams producer for priority-based job enqueue` (`9b986f2`) — `packages/orchestration/producer.py`: `enqueue_job(redis, priority, job)` XADDs `JobMessage.model_dump_json()` to `meridian:reviews:{priority}` (2 unit tests).
   - `feat(orchestration): priority-ordered consumer loop with XREADGROUP` (`da28ece`) — `packages/orchestration/consumer.py`: `process_message` (bytes/str-tolerant parsing, calls async `on_job`) + `consume_loop` (XGROUP CREATE with `mkstream`, reads high → medium → low, `block=5000`, idle debug log; 2 unit tests).
   - `feat(orchestration): ingest_webhook service with advisory lock + idempotency` (`016ef82`) — `packages/orchestration/ingestion.py`: `ingest_webhook` runs inside caller's transaction — advisory lock via `compute_lock_key(repo_id, pr_number, head_sha)`, delivery_id replay check → `IngestResult("replayed")`, else insert `webhook_deliveries` row (`enqueued=false`) → `IngestResult("accepted")` (2 integration tests — skip cleanly without Postgres).
   - `chore: fix pre-existing ruff violations in pre-commit hook script` (`6bf52da`) — E501/SIM102/SIM110 in `scripts/pre_commit/no_env_files.py` (surfaced once the full-worktree gate was run).
2. **Test/lint results (github_orch worktree):** ruff check ✅, ruff format ✅, mypy --strict `packages` ✅ (28 files), **70 passed, 3 skipped** (integration tests skip without Postgres; Docker daemon offline).
3. Pushed `feature/github_orch` to origin (tip `6bf52da`).

### Lessons / gotchas

- The plan's consumer test passed a **sync** lambda as `on_job` but the implementation awaits it (`await None` → TypeError). Fixed the test to use an async handler — the `Callable[..., Awaitable[None]]` contract is the correct one.
- Integration tests skip via the ephemeral-DB fixture before reaching in-function imports, so a missing module wouldn't visibly "fail" — relied on collection errors for unit tests and the fixture's explicit skip message for integration.
- `contextlib.suppress` instead of `try/except/pass` (SIM105) for the pre-existing consumer-group race.

### Next

- [ ] M8 (Tasks 23–25, API app factory + routers) in the `api` worktree.
- [ ] Stacked PRs: `github_orch` → `obs_sec`.

---

## Entry 15 — 2026-09-13: Phase 1 build M8 (Tasks 23–25, API app + routers) in the api worktree

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **API application complete** (`feature/api`, stacked on `feature/github_orch` via `git reset --hard`, 3 commits in the plan's prescribed order 24 → 25 → 23):
   - `feat(api): health (liveness) + ready (readiness) endpoints` (`cc3df70`) — `apps/api/routers/health.py`: `GET /health` (always 200) + `GET /ready` (DB `SELECT 1` + Redis `ping`, returns `not_ready` on failure instead of crashing).
   - `feat(api): POST /v1/webhooks/github with HMAC verify + error envelope` (`7f0ec9c`) — `apps/api/routers/webhooks.py` + `apps/api/errors.py`: thin handler (raw body → headers → 400 missing sig → 401 invalid sig → event/action filter 200 `ignored` → `ingest_webhook` in `session.begin()` → 200 accepted/duplicate; 500 error envelope on internal error); Stripe-style `error_response` (spec §9.3).
   - `feat(api): app factory with lifespan managing DB engine + Redis + GitHub client` (`04d1cc3`) — `apps/api/main.py` (`create_app`, lifespan wiring DB engine + session factory + Redis + `GitHubClient`), `apps/api/deps.py` (`get_settings_dep`, `get_db_session`), `apps/__init__.py` (mypy package-base marker).
2. **Test/lint results (api worktree):** ruff check ✅, ruff format ✅, mypy --strict `packages apps` ✅ (36 files), **77 passed, 3 skipped** (7 new unit tests: app factory 1, health 2, webhooks 4).
3. Pushed `feature/api` to origin (tip `04d1cc3`).

### Lessons / gotchas

- **FastAPI 0.141 differences vs. the plan's code:** `app.routes` no longer exposes nested included-router paths (`_IncludedRouter` has no `.path`) — assert via `app.openapi()["paths"]` instead; `app.router.lifespan_context = None` breaks `TestClient` (`TypeError`) — substitute a no-op async lifespan context manager.
- **`get_settings` is `lru_cached`** — tests that monkeypatch env vars must call `get_settings.cache_clear()` or a later fixture reuses the first test's `GITHUB_WEBHOOK_SECRET` (would corrupt the HMAC test).
- The `get_db_session` dependency resolves `app.state.session_factory` at request time — with lifespan bypassed, fixtures must stub the factory or every webhook test 500s before reaching the handler.
- mypy needed `apps/__init__.py` to avoid dual module resolution (`api.deps` vs `apps.api.deps`).
- `Depends(get_db_session)` in a default argument is FastAPI's canonical DI pattern — suppressed B008 with a comment.

### Next

- [ ] M9–M10 (Tasks 26–29, worker + e2e) in the `worker` worktree.
- [ ] Stacked PRs: `api` → `github_orch`.

---

## Entry 16 — 2026-09-13: Phase 1 build M9–M10 (Tasks 26–29, worker + e2e) in the worker worktree — Phase 1 plan code-complete

**Performed by:** Cline (agent) with Chinmay Duse (psyphon1)

### Done

1. **Worker + e2e complete** (`feature/worker`, stacked on `feature/api` via `git reset --hard`, 5 commits):
   - `feat(worker): main entry point with consumer loop + signal handling` (`b85c4d4`) — `apps/worker/main.py` (`make_consumer_name` = hostname-pid, SIGTERM graceful stop, `asyncio.gather` of the three loops), `apps/worker/consumer.py` (`on_job` fetches payload by delivery_id, marks `processed=true` — full PR upsert deferred to Phase 2 per plan).
   - `feat(worker): transactional outbox publisher with SKIP LOCKED + XADD` (`d1175f3`) — `apps/worker/outbox_publisher.py`: `build_job_message` + `publish_pending` (`SELECT ... FOR UPDATE SKIP LOCKED`, `enqueue_job`, mark `enqueued=true`) + 1s poll loop.
   - `feat(worker): janitor loop with XAUTOCLAIM + XTRIM for stream hygiene` (`327fe69`) — `apps/worker/janitor.py`: 60s cycle claiming idle (>5 min) entries across all three streams + XTRIM (maxlen 10k) incl. dead-letter stream.
   - `test: e2e pipeline test (webhook → outbox row) via ephemeral Postgres fixture` (`6928a52`) — `tests/e2e/test_webhook_to_review_run.py`: signed webhook → API → `webhook_deliveries` row persisted (`enqueued=false`, payload size > 0); skips cleanly without Postgres.
   - `style: ruff format fixes across worker package and tests` (`1bbde3f`).
2. **Test/lint results (worker worktree):** ruff check ✅, ruff format ✅, mypy --strict `packages apps` ✅ (41 files), **80 passed, 4 skipped** (3 new unit tests + 1 e2e; integration + e2e skip without Postgres).
3. **Phase 1 plan status: all 29 tasks implemented.** Full-pipeline behavior (Redis Streams end-to-end, alembic migration on live PG) still requires `docker compose up -d` — integration/e2e suites are written and skip-safe.
4. Pushed `feature/worker` to origin (tip `1bbde3f`).

### Lessons / gotchas

- **Plan bug caught:** Task 27's sample code passes `enqueued_at=func.now()` (a SQLAlchemy clause) into `JobMessage.enqueued_at: str` — Pydantic would reject it. Used `datetime.now(UTC).isoformat()` instead.
- Avoided a circular import (`outbox_publisher` ↔ `main`) by keeping `make_consumer_name` only in `main.py`.
- The janitor test's `fake_sleep` raises `SystemExit` (a `BaseException`) so it escapes the loop's `except Exception` — used `contextlib.suppress(SystemExit)` in the test (also satisfies SIM105).

### Next

- [ ] Open stacked PRs: `github_orch` → `obs_sec`, `api` → `github_orch`, `worker` → `api`.
- [ ] After merges: run `docker compose up -d` + alembic upgrade + integration/e2e suites against live services.
- [ ] Phase 2 backlog: risk-tier classification, installation-token API wiring, pgvector, review agent pipeline.




