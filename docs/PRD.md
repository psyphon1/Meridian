# Meridian — Product Requirements Document (PRD)

**Owner:** Chinmay Duse (psyphon1) · **Version:** 2.0 · **Status:** Approved for build
**Structure follows the standard PRD sections** (problem, goals, users, requirements, success metrics, non-goals) per Atlassian/ClickUp PRD practice.

---

## 1. Problem Statement

First-pass PR review queues behind a small number of senior engineers. Example: 5 developers × 3 PRs/day = 15 PRs behind 2 seniors → context switching, review fatigue, delayed feedback, blocked developers. The manual workflow (ping a senior → supply context → run an AI review → wait for permission to post) wastes senior time on repetitive investigation.

## 2. Goals

1. Landing → working, reviewing installation in **< 5 minutes**.
2. Automatically review every eligible PR on open/update using the user's own LLM key (BYOK).
3. Understand repository-specific context before generating findings.
4. Detect correctness, security, performance, architecture, reliability, and testing risks.
5. **Never publish a BLOCKING/HIGH finding without verifiable evidence** (schema-enforced).
6. Spend minimum tokens per risk tier; spend user's tokens like our own.
7. Escalate high-risk/ambiguous cases to humans.
8. Log every user and system action for audit.
9. Isolate every tenant's code, keys, and execution.

## 3. Target Users

| User | Need |
|---|---|
| Developer | Immediate, actionable, evidence-backed feedback; no opinion-noise |
| Senior Engineer | Reduced first-pass load; only high-signal escalations |
| Tech Lead / Architect | Consistent enforcement of repo architecture rules |
| Account Owner (tenant = user, no RBAC in V1) | Full visibility into spend, keys, retention, audit, deletion |

## 4. User Stories

- **US-01** — As a senior engineer, I want an initial review automatically completed so I spend time only on high-value decisions.
- **US-02** — As a reviewer, I want important areas identified in large/AI-generated PRs.
- **US-03** — As a reviewer, I want auth/billing/migration changes auto-flagged high risk.
- **US-04** — As a developer, I want evidence-backed comments, not stylistic opinions.
- **US-05** — As a new engineer, I want the change explained in the context of existing architecture.
- **US-06** — As a developer, I want serious findings reproduced before they block my PR.
- **US-07** — As a tech lead, I want repo-specific rules enforced, not generic opinions.

## 5. Functional Requirements

- PR open/synchronize webhooks trigger **idempotent** review jobs (unique on `repository_id + pr_number + head_sha`).
- Automatic GitHub review publish per repo policy — no manual "ask permission" step.
- Every finding carries category, severity (BLOCKING/HIGH/MEDIUM/LOW/NIT), confidence, location, evidence state.
- SHA-pinned permalink citation on every published comment.
- `QUEUED_NO_KEY` state visible until a BYOK key exists.
- Per-repo rules, spend caps, and risk configuration via dashboard.

## 6. Non-Goals (V1)

- RBAC / multi-seat orgs · final autonomous merge · auto-modifying production code · non-GitHub SCMs · Meridian-hosted shared inference keys · full autonomous remediation.

## 7. Success Metrics

- **North star:** human-accepted high-value findings ÷ senior-review minutes consumed.
- False-positive rate, human acceptance rate, escalation rate, citation-verifiable rate (target 100% for BLOCKING/HIGH via the evidence gate), median time-to-first-useful-review, cost/PR.

## 8. Release Criteria (V1 launch gate)

Per PRD best practice, V1 is complete only when every item below is verifiably true — anything not listed here will not ship in the release:

1. **Onboarding** — GitHub sign-in → App install → BYOK key → first reviewed PR, end-to-end < 5 minutes on a fresh account, tested on 3 different repos (Python/TS/mixed).
2. **Evidence gate** — 100% of BLOCKING/HIGH findings published in a 50-PR benchmark corpus carry a non-null `evidence_ref` re-derived by the adjudicator; citation permalinks resolve at the pinned SHA.
3. **Reliability** — webhook acknowledgment p99 < 10 s (GitHub terminates slower connections); zero silent drops across a kill-the-worker chaos test (workflows resume from LangGraph checkpoints).
4. **Security** — webhook signature verification reject-test passes (tampered payload → 401, no processing); sandbox egress deny-all verified; key material absent from all logs/traces/exports (automated scan).
5. **Audit** — every user + system action produces a hash-chained audit row; deletion request cascades within the 30-day SLA in a staging drill.
6. **Cost** — per-PR cost metered and visible; per-tenant daily ceiling enforced (synthetic runaway test).
7. **Escalation** — high-risk/ambiguous PRs produce an escalation, not a guess, at the configured rate.

## 9. Assumptions & Dependencies

- GitHub App webhook infrastructure (HTTPS endpoint, secret rotation, IP allowlist from `GET /meta`) is available before Phase 1 closes.
- BYOK users supply keys for a LiteLLM-supported provider (OpenAI/Anthropic/etc.); no Meridian-hosted shared inference keys in V1.
- Tenants accept that tenant = user (no org RBAC) in V1; schema keeps an upgrade path.
- Static analyzers run in-repo (Semgrep rules, CodeQL packs) — analyzer database refresh is an operational dependency.
