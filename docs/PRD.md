# Meridian — Autonomous AI PR Reviewer
# Product Requirements Document (PRD)

**Owner:** Chinmay Duse (psyphon1) · **Version:** 2.1 · **Status:** Approved for build
**Structure follows the standard PRD sections** (problem, goals, users, requirements, success metrics, non-goals) per Atlassian/ClickUp PRD practice.

---

## 1. Problem Statement

Every development team faces the same bottleneck: first-pass PR review queues behind a small number of senior engineers. Example: 5 developers × 3 PRs/day = 15 PRs behind 2 seniors → context switching, review fatigue, delayed feedback, blocked developers. The manual workflow (ping a senior → supply context → run an AI review → wait for permission to post) wastes senior time on repetitive investigation.

**Quantified pain:** In a team of 8, PRs wait an average of 4.2 hours for first review (GitHub Octoverse median). 40% of review comments are stylistic or repetitive (static analysis already caught them). Seniors spend 30-45 min/PR on boilerplate before reaching novel architectural concerns.

Meridian eliminates this bottleneck by becoming the autonomous first-pass senior engineer: it investigates context, reasons about correctness, verifies with deterministic tools, and publishes evidence-backed findings immediately. Humans review only what Meridian escalates or what requires judgment beyond pattern matching.

## 2. Goals

1. **Onboarding → first reviewed PR in < 5 minutes.** A developer installs the GitHub App, adds a BYOK key, and sees a review on their next PR without reading a manual.
2. **Autonomous first-pass review.** Every eligible PR on open/update is reviewed automatically — no "ask permission" step, no manual trigger.
3. **Repository-aware reasoning.** Never evaluate a changed line without relevant repository context (symbol definitions, call graph, architecture rules, historical review memory).
4. **Comprehensive risk coverage.** Detect correctness, security (OWASP ASVS-mapped), performance, architecture, reliability, and testing risks.
5. **Evidence-backed findings only.** `BLOCKING` and `HIGH` severity findings require verifiable evidence (tool run, test execution, or SHA-pinned code span) — schema-enforced, not optional.
6. **Token efficiency.** Spend minimum tokens per risk tier; treat user's BYOK tokens as if they were our own. Risk-adaptive depth: a 2-line typo fix gets a light pass; a 500-line auth refactor gets deep verification.
7. **Human escalation for judgment.** High-risk, ambiguous, or novel findings escalate to humans with full context — never guess when stakes are high.
8. **Full auditability.** Log every user and system action in a tamper-evident, hash-chained audit log.
9. **Tenant isolation.** Every tenant's code, keys, and execution environment is strictly isolated — no cross-tenant data sharing, even transiently.
10. **Bring Your Own Key (BYOK).** Users supply their own LLM API keys; Meridian never hosts shared inference keys. Keys are envelope-encrypted at rest and decrypted only in isolated worker memory at call time.

## 3. Target Users

| User | Need |
|---|---|
| Developer | Immediate, actionable, evidence-backed feedback; no opinion-noise |
| Senior Engineer | Reduced first-pass load; only high-signal escalations |
| Tech Lead / Architect | Consistent enforcement of repo architecture rules |
| Account Owner (tenant = user, no RBAC in V1) | Full visibility into spend, keys, retention, audit, deletion |

## 4. User Stories

- **US-01** — As a senior engineer, I want an initial review automatically completed so I spend time only on high-value architectural decisions, not boilerplate correctness checks.
- **US-02** — As a reviewer, I want important areas identified in large/AI-generated PRs so I don't miss subtle risks in generated code.
- **US-03** — As a reviewer, I want auth/billing/migration changes auto-flagged as high risk so they get deeper scrutiny before merge.
- **US-04** — As a developer, I want evidence-backed comments ("this SQL is injectable — Semgrep rule `sql-injection` matched at line 47") rather than vague opinions ("this looks risky").
- **US-05** — As a new engineer, I want the change explained in the context of existing architecture ("this new endpoint bypasses the rate-limiter middleware defined in `middleware/rate_limit.py`") so I learn while I code.
- **US-06** — As a developer, I want serious findings reproduced before they block my PR — a failing test, a sandbox run, or a Semgrep match I can verify locally.
- **US-07** — As a tech lead, I want repo-specific rules enforced ("all API handlers must call `audit_log.record()`") and not generic style opinions.
- **US-08** — As an account owner, I want to see exactly how many tokens each PR cost, set a daily ceiling, and delete my data with a verified cascade.

## 5. Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-01 | PR open/synchronize webhooks trigger idempotent review jobs | P0 | Unique on `repository_id + pr_number + head_sha`; duplicate delivery is a no-op with 200 ack |
| FR-02 | Automatic GitHub review publish per repo policy | P0 | No manual "ask permission" step; published as a PR review with SHA-pinned permalink citations |
| FR-03 | Every finding carries structured metadata | P0 | Category, severity (`BLOCKING`/`HIGH`/`MEDIUM`/`LOW`/`NIT`), confidence (0.0–1.0), location (`path:Lstart-Lend`), evidence state |
| FR-04 | SHA-pinned permalink on every published comment | P0 | Format: `github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}`; resolves at exact commit |
| FR-05 | `QUEUED_NO_KEY` state visible until BYOK key exists | P0 | Dashboard shows "Add your LLM key to start reviewing" with provider selection |
| FR-06 | Per-repo rules, spend caps, and risk configuration | P1 | Dashboard CRUD for rules; rules affect review output (agent behavior, not just filtering) |
| FR-07 | Real-time review status in dashboard | P1 | Status transitions: `RECEIVED → VALIDATED → QUEUED → CONTEXT_BUILDING → ANALYZING → VERIFYING → ADJUDICATING → PUBLISHING/ESCALATED → COMPLETED` |
| FR-08 | Token/cost meter updating in real time | P1 | Per-PR cost and per-day cumulative spend visible; hard ceiling enforced |
| FR-09 | Escalation queue for human judgment | P1 | Ambiguous or high-risk findings route to escalation queue with full context, not published as fact |
| FR-10 | Account deletion cascades all data | P1 | Verified purge of repo content, symbol index, embeddings, review memory, observability traces within 30-day SLA |

## 6. Non-Goals (V1)

The following are explicitly **out of scope** for V1 to maintain focus and ship velocity. Each is tracked for future roadmap assessment.

- **RBAC / multi-seat orgs** — tenant = user; no role-based access control within an organization.
- **Final autonomous merge** — Meridian never merges; humans retain final authority.
- **Auto-modifying production code** — no autonomous remediation or auto-apply of fixes.
- **Non-GitHub SCMs** — GitHub only; GitLab/Bitbucket/Azure DevOps are post-V1.
- **Meridian-hosted shared inference keys** — BYOK only; no shared key pool managed by Meridian.
- **Full autonomous remediation** — agents identify, humans fix.
- **Real-time collaborative editing** — dashboard is read-only for review status; no inline comment threading.
- **Custom model fine-tuning** — no tenant-specific model training in V1.

## 7. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| **North star** | Human-accepted high-value findings ÷ senior-review minutes consumed | Weekly survey + accepted-finding rate |
| False-positive rate | < 15% | Findings marked "not useful" or dismissed without action |
| Human acceptance rate | > 70% | Findings accepted or acted upon within 7 days |
| Escalation rate | 5–15% | Findings routed to human review (too ambiguous or high-stakes) |
| Citation-verifiable rate | 100% for BLOCKING/HIGH | `evidence_ref` non-null and resolves in benchmark corpus |
| Median time-to-first-useful-review | < 3 min | From webhook delivery to first visible review comment |
| Cost per PR | <$0.50 median | BYOK token spend tracked per-PR |
| Onboarding completion | > 80% | Users who install App → add key → receive first review within 24 h |

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
