# Meridian — Full Session Context / Agent Handoff

## 0. Purpose of this file

This document captures the complete useful context developed in the session so another coding/research agent can continue the Meridian project without needing the prior chat.

**Owner**
- Name: Chinmay Duse
- Handle: psyphon1
- GitHub: https://github.com/psyphon1
- LinkedIn: https://linkedin.com/in/chinmayduse

**Product name:** Meridian

**Primary product:** Production-grade GitHub App for autonomous first-pass PR review.

---

# 1. Core Problem

Today's PR review workflow can create a senior-engineer bottleneck.

Example:

```text
5 developers × 3 PRs
= 15 PRs

Only 2 senior engineers available
→ 15 PRs queue behind 2 reviewers
→ context switching
→ review fatigue
→ delayed feedback
→ developers blocked
```

Typical current workflow:

```text
Developer
   ↓
Creates PR
   ↓
Messages senior engineer
   ↓
Senior opens IDE / coding agent
   ↓
Provides principles/rules/context
   ↓
Agent analyzes PR
   ↓
Agent may take significant time
   ↓
Agent asks permission to post
   ↓
Senior validates output
   ↓
Senior publishes review
```

The proposed solution:

> Automatically perform the first senior-level review whenever a PR is opened/updated, without requiring a senior engineer to initiate the process.

Human engineers remain responsible for final merge decisions.

---

# 2. Product Thesis

Meridian is not simply an “LLM that reviews a diff.”

It is intended to act like:

```text
Senior engineer investigation
        +
Repository intelligence
        +
Specialized review reasoning
        +
Static analysis
        +
Executable evidence
        +
GitHub-native automation
        +
Human escalation
```

Core philosophy:

> Do the investigation automatically, prove important claims, escalate human judgment only where it is valuable, and spend the user's tokens like your own.

A key product positioning:

> **Meridian — the autonomous first-pass engineer for every pull request.**

---

# 3. Desired Product Behavior

When a PR is opened or updated:

```text
GitHub PR
   ↓
GitHub webhook
   ↓
Verify webhook
   ↓
Idempotency
   ↓
Intent Analysis
   ↓
Change Localization
   ↓
Risk Classification
   ↓
Repository Context Gathering
   ↓
Hybrid Retrieval
   ↓
Conditional Multi-Agent Review
   ↓
Evidence Planning
   ↓
Semgrep / CodeQL / Sandbox / Tests
   ↓
Evidence Verification
   ↓
Hallucination / Evidence Gate
   ↓
Confidence + Severity
   ↓
Automatic GitHub Review
   ↓
Escalate high-risk / uncertain findings
```

Important:

**There should be no manual “ask permission to post” step for normal configured operation.**

The GitHub App is authorized to publish its own review.

---

# 4. Main Product Goal

Remove the repetitive first-pass senior-review work.

Before:

```text
15 PRs
 ↓
2 seniors
 ↓
manual queue
```

After:

```text
15 PRs
 ↓
15 automated first-pass reviews in parallel
 ↓
only high-risk / ambiguous cases reach seniors
```

The product does not replace final engineering accountability.

---

# 5. Target Users

### Developer

Needs:
- immediate feedback
- no waiting for senior availability
- actionable comments
- fewer opinion-based comments

### Senior Engineer

Needs:
- reduced review load
- fewer repetitive reviews
- high-signal escalations only
- confidence that automated findings were verified

### Tech Lead / Architect

Needs:
- consistent architecture standards
- repository-specific rules
- security and reliability enforcement
- review consistency

### Account Owner / Tenant

V1 has no RBAC.

One authenticated user is one tenant.

Needs:
- full visibility into usage
- spend
- keys
- data retention
- review activity
- audit history
- deletion

---

# 6. Real User Pain / User Stories

The session researched developer discussions on Reddit and related review pain.

Representative stories:

### US-01 — Reviewer overloaded

As a senior engineer, I want an initial review automatically completed so I can spend time only on high-value engineering decisions.

### US-02 — Large AI-generated PR

As a reviewer, I want Meridian to identify the important areas in a very large PR so I don't have to inspect every line equally.

### US-03 — Sensitive changes

As a reviewer, I want authentication, authorization, billing, migrations and other sensitive changes automatically identified as high risk.

### US-04 — Review noise

As a developer, I want evidence-backed comments instead of subjective stylistic opinions.

### US-05 — Repository understanding

As a developer/new engineer, I want the system to explain how a change interacts with existing architecture and code.

### US-06 — Verified findings

As a developer, I want serious findings reproduced or supported by tools before they block my PR.

### US-07 — Team-specific standards

As a tech lead, I want Meridian to understand repository-specific architecture and review rules rather than applying generic opinions.

---

# 7. Core Product Principles

1. **Context before judgment**
   - Never evaluate changed code only from the diff if meaningful repository context exists.

2. **Evidence over opinion**
   - `HIGH` and `BLOCKING` findings require verifiable evidence.

3. **Risk-adaptive depth**
   - Do not use the same model/tool budget for trivial and critical changes.

4. **Fewer, better comments**
   - Optimize for accepted/actionable findings, not comment volume.

5. **Human remains accountable**
   - Meridian is a first-pass reviewer, not final merge authority.

6. **Tenant isolation**
   - Since V1 has no RBAC, tenant isolation is a primary security boundary.

7. **Spend user's tokens like your own**
   - BYOK means every model call impacts user cost.

---

# 8. High-Level Architecture

```text
                         +-----------------------+
                         |      Next.js UI       |
                         |    Web Dashboard      |
                         +-----------+-----------+
                                     |
                               GitHub OAuth
                                     |
                         +-----------v-----------+
                         |      FastAPI API      |
                         +-----------+-----------+
                                     ^
                                     |
GitHub ----------------------------> |
        PR Webhook                   |
                                     v
                         +-----------------------+
                         | Webhook Verification  |
                         | + Idempotency         |
                         +-----------+-----------+
                                     |
                                     v
                         +-----------------------+
                         | Redis Streams Queue    |
                         | Consumer Groups        |
                         +-----------+-----------+
                                     |
                                     v
                         +-----------------------+
                         | LangGraph Orchestrator |
                         +-----------+-----------+
                                     |
                 +-------------------+-------------------+
                 |                   |                   |
                 v                   v                   v
          Intent + Risk      Repository Context     Review Router
                                     |
              +----------------------+----------------------+
              |                      |                      |
              v                      v                      v
         Tree-sitter             SCIP/LSP              Git History
              |                      |                      |
              +----------------------+----------------------+
                                     |
                                     v
                            Hybrid Retrieval
                         +-----------------------+
                         | BM25 + Dense + Graph  |
                         | Historical + Tests    |
                         +-----------+-----------+
                                     |
                                     v
                            Conditional Agents
           +-----------+-----------+-----------+-----------+
           |           |           |           |           |
           v           v           v           v           v
      Correctness  Security  Performance Architecture Reliability/Test
           +-----------+-----------+-----------+-----------+
                                     |
                                     v
                             Evidence Planner
                                     |
               +---------------------+---------------------+
               |                     |                     |
               v                     v                     v
            Semgrep              CodeQL                Sandbox
                                                         |
                                                         v
                                                   Targeted Tests
               +---------------------+---------------------+
                                     |
                                     v
                              Evidence Verifier
                                     |
                                     v
                                Adjudicator
                                     |
                              +------+------+
                              |             |
                              v             v
                        GitHub Review   Human Escalation
```

---

# 9. Detailed Pipeline

## 9.1 Webhook

```text
GitHub
 ↓
verify signature
 ↓
validate event
 ↓
extract repo + PR + base_sha + head_sha
 ↓
idempotency check
 ↓
persist event
 ↓
enqueue
 ↓
return quickly
```

Idempotency identity:

```text
repository_id + pr_number + head_sha
```

Use database uniqueness.

---

## 9.2 Intent Analysis

Before deep review, determine:

```json
{
  "intent": "...",
  "change_type": "feature|bugfix|refactor|security|migration",
  "affected_components": [],
  "behavior_changed": [],
  "risk_areas": [],
  "uncertainties": []
}
```

Why:
- downstream agents need context
- retrieval should be intent-driven
- risk classification should happen early

---

## 9.3 Change Localization

Transform raw diff into semantic changes:

```text
Git diff
 ↓
Changed files
 ↓
Changed symbols
 ↓
Changed behavior
 ↓
Callers / callees
 ↓
Affected tests
 ↓
Dependency blast radius
```

Use:
- Tree-sitter
- SCIP/LSP

---

# 10. Repository Intelligence

The repository should be indexed and reused across PRs.

Maintain:

```text
File index
Symbol index
Import/dependency graph
Definitions/references
Call graph
Test relationships
Embeddings
Sparse/BM25 index
Repository rules
Historical review memory
Documentation/configuration
```

### Initial indexing

```text
Repository
 ↓
File discovery
 ↓
Tree-sitter
 ↓
Symbol extraction
 ↓
SCIP/LSP
 ↓
Graph construction
 ↓
Embeddings
 ↓
Lexical index
 ↓
Historical memory
 ↓
Persist
```

### Incremental indexing

```text
New commit
 ↓
Changed files
 ↓
Changed symbols
 ↓
Affected dependencies
 ↓
Re-index impacted areas
```

Use a 30–60 second debounce window to prevent index thrashing on rapid force pushes / CI-generated changes.

---

# 11. Retrieval Architecture

Do not use embeddings only.

Use:

```text
BM25
+
Dense embeddings
+
Symbol/code graph
+
Historical review retrieval
+
Test retrieval
 ↓
Fusion
 ↓
Reranker
 ↓
Context selector
```

Priority:

1. Changed symbols
2. Direct callers/callees
3. Related tests
4. Repository rules/docs
5. Historical PR/review evidence
6. Broad context only when uncertainty requires it

Important design principle:

> Embeddings provide relevance; code intelligence provides structural truth.

V1:
- PostgreSQL + pgvector

V2 Qdrant migration trigger:
- p95 retrieval latency > 300ms sustained for 1 hour
OR
- single repository vector count > 5M

---

# 12. Risk Classification

Risk considers:

```text
PR size
+ change type
+ touched subsystem
+ sensitivity
+ dependency blast radius
+ production criticality
+ historical defect density
+ uncertainty
```

Risk tiers:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Risk controls:

- model tier
- context/retrieval budget
- agent selection
- tool execution
- evidence requirements
- escalation
- per-PR token ceiling

---

# 13. Conditional Agent Routing

Do not execute every agent for every PR.

```text
Docs-only
→ skip agents

Config-only
→ Reliability + Architecture

Standard code
→ Correctness + Test + Architecture

Auth / secrets / payment / DB
→ Security deep mode + relevant agents

Hot performance path
→ Performance

Concurrency / migration
→ Reliability deep mode
```

Agents:

- Correctness
- Security
- Performance
- Architecture
- Reliability
- Testing

Agents produce **hypotheses**, not final comments.

---

# 14. Evidence System

Most important differentiator.

Finding flow:

```text
Agent hypothesis
 ↓
Evidence Planner
 ↓
Tool execution
 ↓
Evidence Verifier
 ↓
Adjudicator
 ↓
Publish
```

Evidence priority:

1. Reproduced failure in sandbox.
2. Semgrep / CodeQL result.
3. Concrete control/data-flow trace.
4. Existing failing/insufficient test evidence.
5. Strong repository-grounded reasoning.
6. Pure model intuition.

Pure intuition is never enough for `HIGH` or `BLOCKING`.

---

# 15. Schema-Enforced Publish Gate

Hard rule:

```text
IF severity IN (BLOCKING, HIGH):

    evidence_ref != NULL

    evidence type must be one of:
        tool_run
        test_execution
        sha_pinned_code_span

    adjudicator must re-derive the claim
    from the evidence artifact

ELSE:
    downgrade or suppress
```

This must be an application/schema constraint, not merely a prompt instruction.

Principle:

> Meridian prefers silence over fabricated defects.

Avoid mass LOW/NIT comment spam.

---

# 16. Citations

Every published comment must contain a SHA-pinned GitHub URL:

```text
github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}
```

Purpose:
- source verification
- reproducibility
- stable reference after later pushes
- reduced trust burden

---

# 17. Severity + Escalation

Suggested levels:

```text
BLOCKING
HIGH
MEDIUM
LOW
NIT
```

Escalation based on:

```text
Risk × Confidence × Blast Radius × Repository Policy
```

Escalate:
- critical security
- important migrations
- large architectural changes
- high-risk but uncertain findings
- conflicting evidence
- repo policies requiring human review

---

# 18. Incremental Re-review

For subsequent PR pushes:

```text
New diff
 ↓
Changed symbols
 ↓
Affected dependency graph
 ↓
Reuse unchanged context
 ↓
Reuse prior evidence/findings
 ↓
Review only impacted areas
```

Target:
- no extra spend for unchanged code when technically safe.

---

# 19. BYOK

V1 is Bring Your Own Key.

User supplies own model provider key.

No shared Meridian inference key in V1.

Key handling:

```text
Browser
 ↓ TLS
FastAPI
 ↓
KMS / Vault
 ↓
Encrypted ciphertext
 ↓
Database
```

At runtime:

```text
Ciphertext
 ↓
decrypt inside isolated worker memory
 ↓
LiteLLM request
 ↓
discard / zeroize
```

Never put keys in:
- logs
- traces
- prompts
- GitHub comments
- source
- plaintext DB fields

Support key rotation and multiple providers from V1.

---

# 20. Tenant Isolation

V1:

```text
1 user = 1 tenant
```

No RBAC.

Isolation boundary includes:

```text
repository data
embeddings
review memory
API keys
sandbox runtime
audit data
```

No shared execution runtime between tenants.

---

# 21. Sandbox

Needed for:
- running tests
- building
- reproduction
- generated tests
- executing static-analysis tools

Controls:

```text
CPU limit
Memory limit
Wall-clock timeout
Process limit
Filesystem isolation
Network policy
Temporary workspace
```

Network:
- deny-by-default
- explicit package registry allowlist only when needed

Execution should support stronger Firecracker/gVisor style isolation.

---

# 22. Prompt Injection Defense

Repository code and PR text are untrusted.

Trust hierarchy:

```text
System Policy
 >
Review Policy
 >
Repository Rules
 >
Repository Content
 >
PR/User Content
```

Mechanisms:

- Never put repository content in system/developer role.
- Explicit delimiters.
- Structured JSON outputs.
- Tool allowlists.
- Tool argument validation.
- No unrestricted shell access.
- Repository content cannot change system policy.

---

# 23. Auth Model

Separate GitHub OAuth App and GitHub App.

### GitHub OAuth App

Identity only.

### GitHub App

Repository authorization/access.

Session:
- short-lived JWT
- rotating refresh token
- httpOnly + SameSite cookie

Do not conflate identity auth and repository access.

---

# 24. Queue

Use:

```text
Redis Streams
+
consumer groups
```

Capabilities:

- durable jobs
- retry
- consumer recovery
- dead-letter handling
- tenant concurrency limits
- risk-aware priority
- visibility

Need per-tenant priority lanes so one tenant's burst cannot starve another.

---

# 25. GitHub API Reliability

Implement:

- per-installation token bucket/rate limiting
- request coalescing
- exponential backoff
- secondary-rate-limit handling
- circuit breaker
- delayed queue instead of dropping work

---

# 26. Database Architecture

Core entities:

```text
User
APIKey
Installation
Repository
Commit
File
CodeSymbol
PullRequest
ReviewRun
Finding
Evidence
ToolRun
ReviewMemory
AuditLog
```

Recommended relationships:

```text
USER
  |
  +----< INSTALLATION
            |
            +----< REPOSITORY
                      |
                      +----< FILE
                      |       |
                      |       +----< SYMBOL
                      |
                      +----< PULL_REQUEST
                              |
                              +----< REVIEW_RUN
                                        |
                                        +----< FINDING
                                        |        |
                                        |        +----< EVIDENCE
                                        |
                                        +----< TOOL_RUN
                                        |
                                        +----< AUDIT_EVENT
```

PostgreSQL is source of truth.

pgvector is V1 vector layer.

---

# 27. Audit & Compliance

Audit log must record:

- login
- key add
- key rotate
- key delete
- GitHub install/uninstall
- repo connect/disconnect
- review lifecycle
- finding publication
- configuration changes
- export
- deletion requests

Audit store:
- append-only
- hash-chained
- separate from mutable operational data
- redacted

Retention:
- configurable
- sane default around 90 days from prior design
- user-configurable within policy
- actual deletion must cascade across repo data/index/embeddings/review memory/traces

Baseline assumed:
- SOC2-shaped security controls
- encryption
- access logging
- retention/deletion controls

If formal GDPR/HIPAA/etc. compliance is needed, update design.

---

# 28. Production Architecture

```text
                        Website / Dashboard
                               |
                       GitHub OAuth identity
                               |
                               v
                         FastAPI Gateway
                        /              \
                       /                \
             GitHub App Webhook       Dashboard API
                     |
              signature verify
              rate limiting
              idempotency
                     |
                     v
          Redis Streams / Priority Queue
                     |
                     v
              LangGraph Workflow
                     |
          +----------+----------+
          |                     |
          v                     v
 Context Intelligence       Risk Engine
          |                     |
          v                     v
 Tree-sitter / SCIP        Review Strategy
          |                     |
          +----------+----------+
                     |
                     v
              Review Agents
                     |
                     v
              Evidence Planner
                /       \
               v         v
          Semgrep      CodeQL
               \         /
                \       /
                 v     v
                Sandbox
                   |
                   v
                Tests
                   |
                   v
                Verification
                   |
                   v
               Adjudication
                   |
                   v
             GitHub Review
                   |
                   v
             Human Escalation

Supporting:
PostgreSQL + pgvector
KMS/Vault
OpenTelemetry + Langfuse
Terraform
Docker/Kubernetes
GitHub Actions
```

---

# 29. Technology Stack & Why

| Technology | Role | Reason |
|---|---|---|
| Next.js + TypeScript | Web dashboard | modern React stack and strong developer tooling |
| GitHub OAuth App | Identity | separate identity from repo access |
| GitHub App | Repo integration | installation-scoped permissions and webhooks |
| FastAPI | API | async Python + AI tooling ecosystem |
| LangGraph | orchestration | explicit stateful workflow/checkpoint model |
| Redis Streams | queue | durable consumer-group workflow |
| Tree-sitter | parsing | incremental multi-language AST |
| SCIP/LSP | code intelligence | precise definitions/references |
| PostgreSQL | database | transactional system of record |
| pgvector | V1 vectors | vector retrieval without immediate separate DB |
| Qdrant | V2 | dedicated retrieval when scale/latency threshold reached |
| BM25 | lexical search | exact code identifier matching |
| Reranker | retrieval | improve context precision |
| LiteLLM | LLM gateway | multi-provider abstraction + BYOK |
| vLLM | optional inference | self-hosted inference |
| Semgrep | analysis | fast deterministic checks |
| CodeQL | semantic security | deep data-flow/security evidence |
| Sandbox | execution | safe testing/reproduction |
| KMS/Vault | secrets | envelope-encrypted keys |
| OpenTelemetry | observability | standard tracing/metrics |
| Langfuse | LLM visibility | AI traces/evaluation |
| Terraform | IaC | reproducible infrastructure |
| Docker/Kubernetes | runtime | deployment/isolation |
| GitHub Actions | CI/CD | native automation |

---

# 30. API Layer

Suggested endpoints:

```text
POST   /api/webhooks/github

GET    /api/me

GET    /api/repositories
POST   /api/repositories/{id}/connect
PATCH  /api/repositories/{id}/config

GET    /api/reviews
GET    /api/reviews/{id}
GET    /api/reviews/{id}/findings
GET    /api/reviews/{id}/evidence

POST   /api/keys
POST   /api/keys/{id}/rotate
DELETE /api/keys/{id}

GET    /api/audit
POST   /api/data-deletion
```

All APIs:
- OpenAPI
- versioned
- validated
- authenticated where required
- rate limited
- correlation IDs
- consistent errors
- no secrets in errors

---

# 31. UI / UX

Primary dashboard:

```text
Overview
Repositories
Review Runs
Findings
Rules
Spend
Audit
Settings
```

Review detail should show:

```text
Summary
Risk
Duration
Files analyzed
Findings
Evidence
Verification
Context
Escalation
```

Important UX rule:

> User should be able to answer “Why did Meridian comment?” in under 30 seconds.

Do not expose chain-of-thought.

Expose:
- evidence
- source
- verification
- concise rationale
- recommendation

---

# 32. Observability

Trace:

```text
Webhook
 → Intent
 → Localization
 → Retrieval
 → Agent
 → Tool
 → Sandbox
 → Adjudication
 → Publish
```

Track:
- latency per stage
- token usage
- retrieval quality
- tool execution
- retries
- evidence success
- false positive rate
- accepted/rejected findings
- cost/PR
- escalation rate
- queue depth

No raw repository code/secrets in shared telemetry.

---

# 33. Cost Strategy

Risk-adaptive:

```text
LOW
→ small model
→ lightweight retrieval
→ skip irrelevant agents

MEDIUM
→ standard model
→ hybrid retrieval

HIGH
→ strong reasoning
→ static analysis
→ targeted execution

CRITICAL
→ strongest model
→ deep retrieval
→ full execution
→ human escalation
```

Optimization:
- prompt caching
- repository context caching
- conditional agents
- incremental re-review
- context slicing
- per-tenant daily spend ceiling
- per-PR token ceiling
- CRITICAL pre-flight estimate

---

# 34. Reliability

Requirements:

- duplicate webhook cannot create duplicate review
- bounded retries
- workflow checkpointing
- explicit PARTIAL_REVIEW
- visible queue/sandbox exhaustion
- GitHub rate-limit backoff
- delayed queue instead of silent drop

Suggested statuses:

```text
RECEIVED
VALIDATED
QUEUED
QUEUED_NO_KEY
CONTEXT_BUILDING
ANALYZING
VERIFYING
ADJUDICATING
PUBLISHING
ESCALATED
PARTIAL_REVIEW
COMPLETED
FAILED
```

---

# 35. Performance Targets

| Metric | Target |
|---|---:|
| Webhook → queued | < 10 sec |
| Standard review P50 | < 3 min |
| Standard review P95 | < 8 min |
| Deep/Critical review P95 | < 15 min |
| Webhook availability | 99.9% |
| Signup → first repo connected | < 5 min |

---

# 36. Evaluation

Benchmark should contain:
- historical PRs
- human review comments
- merged/reverted examples
- known defects
- security cases
- negative examples

Metrics:
- precision
- recall
- false positive rate
- human acceptance rate
- review latency
- escalation rate
- citation-verifiable rate
- cost/PR

North-star:

```text
Human-accepted high-value findings
----------------------------------
Senior-review minutes consumed
```

Critical extra metric:

```text
Percentage of BLOCKING/HIGH findings
whose evidence independently reproduces
the claim during audit.
```

Target:
100% due to schema-enforced gate.

---

# 37. Quality Gates

V1 must satisfy:

- No HIGH/BLOCKING without evidence.
- Every published finding has SHA-pinned citation.
- Duplicate findings are deduplicated.
- Review reproducible from commit SHA and versioned config.
- Repository rules affect review.
- Security-sensitive PRs get deeper checks.
- Sandbox is tenant isolated.
- Failed analysis is visible.
- Review latency is observable.
- User key never appears in logs/traces/exports.
- Data deletion is verifiable.

---

# 38. Failure Modes

| Failure | Response |
|---|---|
| LLM hallucination | evidence gate + confidence filtering |
| Missing context | graph-aware retrieval + uncertainty escalation |
| Prompt injection | trust-boundary enforcement |
| High latency | adaptive depth + incremental indexing + debounce |
| Duplicate webhook | idempotency + DB unique constraint |
| Bad architectural assumption | historical context + human escalation |
| Tool unavailable | PARTIAL_REVIEW |
| Sandbox exhaustion | visible queue |
| GitHub rate limit | backoff + delayed queue |
| Key leak risk | encrypted storage + memory-only runtime |
| Runaway spend | hard spend ceiling |

---

# 39. Definition of Done

V1 is complete when a user can:

1. Sign in through GitHub.
2. Install Meridian on a repository.
3. Configure model provider/key.
4. Set repo review rules and spend cap.
5. Open a PR.
6. See live review state.
7. Receive an automatic GitHub review.
8. See evidence/citations for HIGH/BLOCKING findings.
9. See exact spend.
10. See audit history.
11. Delete their data.
12. Reconstruct the review from the PR commit SHA.

---

# 40. Project Structure

```text
meridian/
├── apps/
│   ├── api/
│   ├── worker/
│   ├── web/
│   └── github-app/
│
├── packages/
│   ├── agents/
│   ├── orchestration/
│   ├── code-intelligence/
│   ├── retrieval/
│   ├── evidence/
│   ├── analyzers/
│   ├── sandbox/
│   ├── github/
│   ├── risk-engine/
│   ├── models/
│   ├── security/
│   ├── observability/
│   └── config/
│
├── services/
│   ├── repository-indexer/
│   ├── review-engine/
│   ├── evidence-engine/
│   ├── notification-service/
│   └── audit-service/
│
├── infra/
│   ├── terraform/
│   ├── kubernetes/
│   ├── docker/
│   └── sandbox/
│
├── db/
│   ├── migrations/
│   ├── seeds/
│   └── schema/
│
├── docs/
├── prompts/
├── evals/
├── tests/
├── scripts/
├── .github/
├── .env.example
├── Makefile
├── pyproject.toml
├── package.json
├── pnpm-workspace.yaml
├── docker-compose.yml
└── README.md
```

---

# 41. Code Standards

Python:
- Ruff
- strict typing where practical
- pytest
- explicit errors
- PEP 8

TypeScript:
- strict TypeScript
- ESLint
- Prettier
- component/unit tests

API:
- OpenAPI
- versioned endpoints
- consistent errors

Git:
- protected main
- Conventional Commits
- CI-required PRs
- CODEOWNERS

Security:
- dependency scanning
- secret scanning
- SAST
- SBOM

---

# 42. Developer Standards

- Feature begins with issue + acceptance criteria.
- PRs remain reviewable.
- Behavior changes include tests.
- Architecture changes require ADR.
- Production bugs get regression tests where practical.
- Observability is part of Definition of Done.
- No credentials in source/images/logs.

---

# 43. Agent Standards

Agents:

- have narrow responsibilities
- use explicit schemas
- output hypotheses
- cite source locations
- separate facts/inference/recommendation
- cannot invent repository conventions
- use allowlisted tools only
- have token/iteration limits
- are traceable by review-run ID
- cannot bypass evidence/adjudication for critical findings

---

# 44. Prompt Architecture

```text
prompts/
├── system/
├── review/
│   ├── correctness.md
│   ├── security.md
│   ├── performance.md
│   ├── architecture.md
│   ├── reliability.md
│   └── testing.md
├── evidence/
└── adjudication/
```

Prompts are version-controlled artifacts.

---

# 45. Evaluation Architecture

```text
Historical PR Dataset
        |
        +-- bugs
        +-- security
        +-- architecture
        +-- negative cases
        +-- human comments
        |
        v
Benchmark
        |
        +--> precision
        +--> recall
        +--> false positives
        +--> acceptance
        +--> evidence rate
        +--> latency
        +--> cost
```

Any model/prompt/retrieval change should run regression evaluation before deployment.

---

# 46. Implementation Roadmap

## Phase 1 — Foundation

- GitHub App
- OAuth
- FastAPI
- PostgreSQL
- Redis Streams
- PR retrieval
- basic GitHub review publishing

## Phase 2 — BYOK + Isolation

- KMS/Vault
- per-request key injection
- tenant isolation
- key management dashboard

## Phase 3 — Repository Intelligence

- Tree-sitter
- SCIP/LSP
- indexing
- pgvector
- hybrid retrieval
- repository rules

## Phase 4 — Review Intelligence

- Intent
- Risk
- Correctness
- Security
- Architecture
- Test agents
- conditional routing

## Phase 5 — Evidence

- Semgrep
- CodeQL
- sandbox
- targeted execution
- evidence gate
- SHA-pinned citations

## Phase 6 — Productionization

- escalation
- OpenTelemetry
- Langfuse
- cost control
- idempotency
- rate limiting
- audit logging
- benchmark

## Phase 7 — V2

- review memory
- Qdrant migration
- vLLM
- advanced graph reasoning
- organization/RBAC
- analytics
- closed-loop remediation later

---

# 47. Naming / Branding

Accepted product name:

> **Meridian**

Why:
- not locked to “AI”
- not locked to “PR”
- can expand into broader engineering intelligence
- strong infrastructure/product feel

Potential product structure:

```text
Meridian
├── Meridian Review
├── Meridian Verify
├── Meridian Risk
└── Meridian Insights
```

---

# 48. Documentation Artifacts Already Created

Files created during session:

- `Meridian_Design_Doc_Final.html`
- `Meridian_TRD.md`
- `Meridian_SDD.md`
- `Meridian_Architecture.md`
- `Meridian_PROJECT_STRUCTURE.md`
- `Meridian_Documentation_Template.html`
- `Meridian_Documentation_Smooth_ASCII.html`

The final HTML documentation was based on the referenced documentation template:

https://github.com/surjithctly/documentation-html-template

It was updated to:
- documentation-style sidebar
- nested sections
- smooth scroll/reveal animations
- ASCII diagrams instead of Mermaid

---

# 49. Important Source-of-Truth Attachment

A complete Meridian v2 specification was provided in the session and contains 27 numbered sections covering:

- Executive summary
- Problem
- Goals
- Users
- Onboarding
- Principles
- Repository intelligence
- Retrieval
- Review pipeline
- Agents
- Risk
- Incremental re-review
- Evidence gate
- Severity/escalation
- Tenant isolation
- Compliance/audit
- Production architecture
- Technology stack
- Data model
- Security/reliability
- Cost/token efficiency
- Observability
- Evaluation
- Quality gates
- MVP
- Failure modes
- Definition of Done
- Product thesis

Critical source details include:

- BYOK
- no RBAC V1
- tenant = user
- `QUEUED_NO_KEY`
- evidence/citation gate
- SHA-pinned GitHub links
- per-tenant execution boundary
- Redis Streams priority lanes
- KMS-backed secret handling
- Firecracker/gVisor direction
- deny-all sandbox egress
- GitHub API rate limiter
- append-only hash-chained audit logs
- 90-day-style configurable retention baseline
- p95 retrieval >300ms / >5M vectors as Qdrant trigger
- exact V1 SLA targets
- exact V1 quality gates
- incremental re-review
- conditional agents
- final Definition of Done

Use the attached source document as authoritative if details conflict with older drafts.

---

# 50. Important Engineering Judgment

The strongest design decision is:

```text
Do NOT build:
Diff → LLM → comments

Build:
PR
 ↓
Context
 ↓
Code Graph
 ↓
Risk
 ↓
Specialized Reasoning
 ↓
Evidence
 ↓
Verification
 ↓
Adjudication
 ↓
Publish / Escalate
```

The moat is not the choice of frontier model.

The moat is:

```text
Repository understanding
+
historical/team memory
+
code graph
+
risk-adaptive execution
+
evidence verification
+
low-noise publishing
+
automatic escalation
```

---

# 51. Recommended Immediate Next Steps

After this handoff, the recommended build order is:

```text
1. Finalize ADRs
2. Define DB schema/migrations
3. Define Pydantic/domain schemas
4. Define GitHub App permissions/webhooks
5. Build webhook → Redis pipeline
6. Build LangGraph review state machine
7. Implement repository indexing
8. Implement retrieval
9. Implement first correctness/security agents
10. Implement evidence gate
11. Implement Semgrep/CodeQL adapters
12. Implement sandbox
13. Implement GitHub publisher
14. Build dashboard
15. Build evaluation benchmark
16. Production hardening
```

Start with deterministic infrastructure and domain contracts before investing heavily in agent prompts.

---

# 52. One-Sentence Product Definition

> **Meridian automatically performs the first senior-level PR investigation for every GitHub pull request, using repository-wide context, specialized AI reasoning and verifiable evidence, then publishes the review and escalates only the decisions that still require human judgment.**
