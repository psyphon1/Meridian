# Meridian — System Design Document (SDD)

**Product:** Meridian  
**Owner:** Chinmay Duse (psyphon1)  
**GitHub:** https://github.com/psyphon1  
**LinkedIn:** https://linkedin.com/in/chinmayduse  
**Version:** 2.0  
**Status:** Final

---

## 1. System Purpose

Meridian is an autonomous first-pass GitHub Pull Request reviewer.

Its job is to remove the repetitive senior-review bottleneck:

```text
Developer opens PR
      ↓
Senior requested manually
      ↓
Senior opens IDE / coding agent
      ↓
Context + rules supplied
      ↓
AI review executed
      ↓
Senior validates output
      ↓
Review published
```

Meridian changes this to:

```text
Developer opens PR
      ↓
GitHub webhook
      ↓
Meridian automatically gathers context
      ↓
Risk-aware multi-agent analysis
      ↓
Evidence verification
      ↓
Automatic GitHub review
      ↓
Senior sees only high-risk / uncertain cases
```

---

# 2. Design Goals

### Primary

- Repository-aware PR review.
- Autonomous first-pass review.
- Evidence-backed findings.
- Low hallucination rate.
- Risk-adaptive compute.
- Token-efficient BYOK operation.
- Deterministic verification.
- Human escalation for high-impact uncertainty.
- Strong tenant isolation.
- Full auditability.
- Reproducible review from a commit SHA.

### Non-goals

- Final autonomous merge authority.
- Autonomous production code modification in V1.
- Arbitrary repository command execution.
- Multi-SCM support in V1.
- Shared Meridian model keys in V1.

---

# 3. Architectural Principles

## 3.1 Separation of concerns

```text
LLM
= reasoning

Tree-sitter
= syntax / AST understanding

SCIP / LSP
= structural code relationships

Retrieval
= relevant contextual evidence

Semgrep / CodeQL
= deterministic analysis

Sandbox
= executable verification

PostgreSQL
= source of truth

LangGraph
= workflow orchestration

GitHub App
= SCM boundary

Human
= final authority
```

## 3.2 Trust boundaries

```text
System Policy
      >
Review Policy
      >
Repository Rules
      >
Repository Content
      >
PR / User Content
```

Repository content is always untrusted data.

---

# 4. High-Level Architecture

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

# 5. Runtime Components

## 5.1 Web Dashboard

Responsibilities:

- GitHub authentication.
- GitHub App installation flow.
- BYOK configuration.
- Repository configuration.
- Live review status.
- Finding inspection.
- Evidence inspection.
- Spend visibility.
- Audit visibility.
- Data deletion.

The dashboard is the user-facing control plane.

---

# 6. Authentication Architecture

Authentication uses two separate GitHub concerns.

## Identity

```text
User
 ↓
GitHub OAuth App
 ↓
Application session
```

The OAuth application is used only for identity.

## Repository authorization

```text
User
 ↓
Install GitHub App
 ↓
installation_id
 ↓
Repository access
```

The identity OAuth client and GitHub App credentials must never be conflated.

---

# 7. Webhook Gateway

Responsibilities:

1. Receive GitHub event.
2. Validate webhook signature.
3. Validate supported event.
4. Extract repository/PR metadata.
5. Resolve tenant.
6. Apply idempotency.
7. Persist event.
8. Create review job.
9. Return quickly.

### Idempotency

```text
(repository_id, pr_number, head_sha)
```

must be uniquely constrained.

Duplicate events must not create duplicate review runs.

---

# 8. Queue Architecture

Redis Streams with consumer groups are used.

```text
                 +----------------+
Webhook -------->| Redis Stream   |
                 +-------+--------+
                         |
            +------------+-------------+
            |            |             |
            v            v             v
        Worker A     Worker B      Worker C
```

Requirements:

- Durable jobs.
- Consumer recovery.
- Retry.
- Dead-letter queue.
- Tenant concurrency limits.
- Risk-aware priority.
- Queue visibility.

Per-tenant priority lanes prevent one user's PR burst from starving other tenants.

---

# 9. Review Orchestrator

LangGraph coordinates the review state machine.

```text
RECEIVED
   ↓
VALIDATED
   ↓
QUEUED
   ↓
CONTEXT_BUILDING
   ↓
ANALYZING
   ↓
VERIFYING
   ↓
ADJUDICATING
   ↓
PUBLISHING
   ↓
COMPLETED
```

Alternative terminal states:

```text
ESCALATED
PARTIAL_REVIEW
FAILED
```

Every expensive stage should checkpoint state.

---

# 10. Review State Machine

```text
           +-----------+
           | RECEIVED  |
           +-----+-----+
                 |
                 v
           +-----------+
           | VALIDATED |
           +-----+-----+
                 |
                 v
           +-----------+
           |  QUEUED   |
           +-----+-----+
                 |
                 v
      +---------------------+
      | CONTEXT_BUILDING    |
      +----------+----------+
                 |
                 v
           +-----------+
           | ANALYZING |
           +-----+-----+
                 |
                 v
           +-----------+
           | VERIFYING |
           +-----+-----+
                 |
                 v
         +---------------+
         | ADJUDICATING  |
         +-------+-------+
                 |
          +------+------+
          |             |
          v             v
     PUBLISHING     ESCALATED
          |             |
          +------+------+
                 |
                 v
           +-----------+
           | COMPLETED |
           +-----------+
```

---

# 11. Repository Intelligence Service

This is one of Meridian's core components.

It builds a reusable repository representation.

## Inputs

- Git repository.
- PR commits.
- Repository docs.
- Configuration.
- Existing tests.
- Repository instructions.
- Git history.
- Previous review information.

## Outputs

```text
File Index
Symbol Index
Code Graph
Dependency Graph
Test Graph
Repository Rules
Historical Review Memory
Embedding Index
Lexical Index
```

---

# 12. Repository Indexing

## Full indexing

Used on initial repository connection.

```text
Repository
   ↓
File discovery
   ↓
Tree-sitter parsing
   ↓
Symbol extraction
   ↓
SCIP/LSP relationships
   ↓
Dependency graph
   ↓
Embeddings
   ↓
Lexical index
   ↓
Persist
```

## Incremental indexing

On new commits:

```text
Commit
 ↓
Changed files
 ↓
Changed symbols
 ↓
Affected dependencies
 ↓
Re-index only impacted portions
```

Use a 30–60 second debounce window for rapid repository updates to avoid index thrashing.

---

# 13. Code Intelligence

## Tree-sitter

Used to identify:

- Functions.
- Classes.
- Methods.
- Imports.
- Syntax structure.
- Changed semantic regions.

## SCIP/LSP

Used to resolve:

- Definitions.
- References.
- Callers.
- Callees.
- Implementations.
- Symbol relationships.

The system should never depend only on textual or semantic similarity for program relationships.

---

# 14. Change Localization

The system converts the raw diff into semantic changes.

```text
Git diff
   ↓
Changed files
   ↓
Changed symbols
   ↓
Changed behavior
   ↓
Affected callers/callees
   ↓
Affected tests
   ↓
Dependency blast radius
```

This becomes the retrieval query for downstream agents.

---

# 15. Retrieval Architecture

Meridian uses hybrid retrieval.

```text
                  Query
                    |
      +-------------+-------------+
      |             |             |
      v             v             v
    BM25          Dense        Code Graph
      |             |             |
      +-------------+-------------+
                    |
             Historical Reviews
                    |
               Test Retrieval
                    |
                    v
                  Fusion
                    |
                    v
                Reranker
                    |
                    v
             Context Selection
```

Retrieval should be hierarchical:

```text
Changed symbol
   ↓
Direct dependencies
   ↓
Tests
   ↓
Rules/docs
   ↓
Historical context
   ↓
Broader context only if required
```

---

# 16. Review Intent Agent

The intent agent produces structured output:

```json
{
  "intent": "...",
  "change_type": "feature",
  "affected_components": [],
  "behavior_changed": [],
  "risk_areas": [],
  "uncertainties": []
}
```

The intent output determines retrieval and review strategy.

---

# 17. Risk Engine

Risk score:

```text
PR size
+ change type
+ subsystem
+ sensitivity
+ dependency blast radius
+ production criticality
+ historical defect density
+ uncertainty
```

Risk tier:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Risk tier determines:

- Model.
- Context size.
- Agent count.
- Tool usage.
- Verification depth.
- Token budget.
- Human escalation.

---

# 18. Conditional Agent Router

```text
Change Type
     |
     +-- docs-only --------> skip agents
     |
     +-- config -----------> Reliability + Architecture
     |
     +-- standard code ----> Correctness + Test + Architecture
     |
     +-- auth/security ----> Security deep mode
     |
     +-- database ----------> Reliability + Security where relevant
     |
     +-- concurrency -------> Reliability deep mode
     |
     +-- hot path ----------> Performance
```

Agents must not execute unnecessarily.

---

# 19. Specialized Review Agents

## Correctness Agent

Checks:

- Logic errors.
- Edge cases.
- Invalid state.
- Error handling.
- Race conditions.
- Regression risk.

## Security Agent

Checks:

- Authentication.
- Authorization.
- Injection.
- Secrets.
- Data exposure.
- Unsafe dependencies.
- Trust-boundary violations.

## Performance Agent

Checks:

- Complexity.
- N+1 queries.
- Excessive I/O.
- Memory growth.
- Cache behavior.
- Scaling risk.

## Architecture Agent

Checks:

- Layer violations.
- Coupling.
- Abstraction quality.
- API boundaries.
- Repository conventions.

## Reliability Agent

Checks:

- Retries.
- Timeouts.
- Idempotency.
- Partial failures.
- Queue semantics.
- Distributed-system failure modes.

## Testing Agent

Checks:

- Missing scenarios.
- Regression protection.
- Test quality.
- Boundary cases.
- Testability.

---

# 20. Agent Contract

Agents cannot directly publish GitHub comments.

They output structured hypotheses:

```json
{
  "category": "security",
  "claim": "...",
  "location": {
    "file": "...",
    "line": 123
  },
  "severity_candidate": "HIGH",
  "reasoning_summary": "...",
  "evidence_needed": []
}
```

These hypotheses must enter the evidence pipeline.

---

# 21. Evidence Planner

The Evidence Planner converts a hypothesis into verification tasks.

Example:

```text
Hypothesis:
"User-controlled input reaches SQL query."

Planner:
  1. Trace input source.
  2. Trace data transformations.
  3. Identify SQL sink.
  4. Run CodeQL query.
  5. Run targeted reproduction if possible.
```

---

# 22. Evidence Engine

Evidence hierarchy:

```text
1. Reproduced failure
2. Semgrep / CodeQL result
3. Concrete control/data-flow trace
4. Existing failing test
5. Repository-grounded semantic reasoning
6. Pure model intuition
```

Pure intuition is never sufficient for blocking/high findings.

---

# 23. Sandbox Architecture

```text
Review Worker
     |
     v
Sandbox Scheduler
     |
     v
+-----------------------+
| Isolated Runtime      |
|                       |
| repo snapshot         |
| tests                 |
| tools                 |
| temporary filesystem  |
+-----------+-----------+
            |
            v
        result/evidence
```

Execution constraints:

- CPU limit.
- Memory limit.
- Wall-clock limit.
- Process limit.
- Filesystem isolation.
- Network policy.
- Ephemeral workspace.

Network egress defaults to deny-all.

---

# 24. Evidence Verifier

The verifier receives:

```text
Finding Hypothesis
+
Evidence Artifact
+
Repository Context
```

It determines:

```text
VERIFIED
UNVERIFIED
CONTRADICTED
PARTIAL
```

The verifier must derive the conclusion from evidence rather than blindly trusting originating-agent prose.

---

# 25. Adjudication

The adjudicator consolidates:

```text
Agent hypotheses
+
Evidence
+
Repository rules
+
Risk
+
Confidence
+
Blast radius
```

Output:

```text
SUPPRESS
INFO
LOW
MEDIUM
HIGH
BLOCKING
ESCALATE
```

---

# 26. Publish Gate

Hard application rule:

```text
IF severity = HIGH or BLOCKING:

    evidence_ref must exist

    evidence type must be:
      - tool_run
      - test_execution
      - sha_pinned_code_span

    evidence must be independently verified

ELSE:

    downgrade or suppress
```

This rule must be enforced in code/schema.

---

# 27. GitHub Review Publisher

Publisher:

1. Converts validated findings to GitHub comments.
2. Adds severity.
3. Adds confidence.
4. Adds concise explanation.
5. Adds recommendation.
6. Adds evidence link.
7. Uses SHA-pinned source URL.
8. Creates review state.

Example source:

```text
github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}
```

---

# 28. Human Escalation

Escalation score:

```text
Risk × Confidence × Blast Radius × Repository Policy
```

Escalate when:

- Critical security risk.
- High-impact migration.
- Core architectural change.
- Uncertain but potentially catastrophic finding.
- Conflicting evidence.
- Repository policy requires senior review.

---

# 29. Incremental PR Re-review

For a new push:

```text
Previous Review
      |
      v
New Diff
      |
      v
Changed Symbols
      |
      v
Dependency Impact
      |
      v
Reuse Unchanged Context
      |
      v
Reuse Unchanged Findings
      |
      v
Review Only Impacted Areas
```

This is essential for token efficiency.

---

# 30. BYOK Architecture

User model keys are submitted through the dashboard.

```text
Browser
  |
 TLS
  v
FastAPI
  |
  v
KMS Envelope Encryption
  |
  v
Ciphertext Storage
```

At runtime:

```text
Encrypted Key
   ↓
Decrypt in worker memory
   ↓
LiteLLM request
   ↓
Discard / zeroize
```

Keys must never appear in:

- Logs.
- Traces.
- Database plaintext.
- Prompt content.
- GitHub comments.
- Error messages.

---

# 31. Tenant Isolation

Tenant = user in V1.

Isolation applies to:

```text
Database rows
+
Vector data
+
Repository snapshots
+
Model keys
+
Sandbox execution
+
Audit data
```

Execution should use tenant-scoped namespaces or stronger microVM isolation.

No tenant's repository code or secret should share a runtime with another tenant.

---

# 32. Prompt Injection Defense

Repository content is explicitly treated as untrusted.

Rules:

```text
System policy
>
Review policy
>
Repository rules
>
Repository data
>
PR text
```

Implementation:

- Repository content never enters system/developer prompt roles.
- Use explicit data delimiters.
- Structured output schemas.
- Tool allowlists.
- Tool argument validation.
- No unrestricted shell access.
- No repository content can modify system policy.

---

# 33. Database Architecture

```text
                        USER
                          |
                          v
                    INSTALLATION
                          |
                          v
                      REPOSITORY
           +--------------+---------------+
           |              |               |
           v              v               v
          FILE          RULE        REVIEW_MEMORY
           |
           v
        SYMBOL
           |
           v
      PULL_REQUEST
           |
           v
       REVIEW_RUN
       /    |     \
      /     |      \
     v      v       v
 FINDING  TOOL_RUN  AUDIT_EVENT
    |
    v
 EVIDENCE
```

PostgreSQL is the canonical source of truth.

pgvector is used for V1 embeddings.

---

# 34. Transaction Boundaries

## Webhook

```text
validate
→ idempotency insert
→ enqueue
```

The event must be committed before it can be considered accepted.

## Finding

```text
candidate
→ evidence
→ adjudication
→ publish state
```

No `BLOCKING/HIGH` finding can transition to publishable state without evidence.

---

# 35. Consistency Requirements

Critical operations require transactional guarantees:

- Review creation.
- Idempotency.
- Finding publish state.
- Evidence status.
- Installation ownership.
- Key metadata updates.

External GitHub operations must be modeled as retryable side effects.

---

# 36. Failure Handling

| Failure | System behavior |
|---|---|
| Duplicate webhook | Ignore duplicate |
| LLM timeout | Retry with bounded backoff |
| Tool timeout | Retry or mark unavailable |
| Sandbox unavailable | Queue / partial review |
| GitHub rate limit | Backoff + delayed queue |
| Missing context | Retrieval expansion / uncertainty |
| Evidence unavailable | Suppress/downgrade |
| Worker crash | Resume from checkpoint |
| Spend ceiling reached | Stop and notify |
| Key unavailable | `QUEUED_NO_KEY` |

---

# 37. GitHub API Rate-Limit Flow

```text
GitHub API
    |
    v
Rate limiter
    |
    +--> success --> continue
    |
    +--> rate limited
              |
              v
         exponential backoff
              |
              v
          retry queue
              |
         +----+----+
         |         |
      success   circuit open
                   |
                   v
             delayed state
```

---

# 38. Observability Architecture

```text
API / Workers / Tools / Sandbox
              |
              v
      OpenTelemetry
              |
              v
       Collector
              |
       +------+------+
       |             |
       v             v
    Metrics        Traces
       |             |
       +------+------+
              |
              v
          Langfuse
```

Track:

- Webhook latency.
- Queue latency.
- Retrieval latency.
- Agent latency.
- Tool latency.
- Sandbox duration.
- Token usage.
- Cost.
- Evidence success.
- False positives.
- Acceptance rate.
- Escalation rate.

Raw code and secrets must be redacted.

---

# 39. UI Architecture

```text
Dashboard
   |
   +-- Overview
   |
   +-- Repositories
   |      |
   |      +-- Configuration
   |      +-- Index status
   |
   +-- Reviews
   |      |
   |      +-- Review detail
   |             +-- Findings
   |             +-- Evidence
   |             +-- Context
   |             +-- Status
   |
   +-- Rules
   |
   +-- API Keys
   |
   +-- Spend
   |
   +-- Audit
```

Review detail should answer:

> What changed?  
> Why was it risky?  
> What evidence supports the finding?  
> What should I do?

Do not expose chain-of-thought.

---

# 40. Security Architecture

Security controls:

```text
GitHub permissions
        ↓
Webhook verification
        ↓
Tenant authorization
        ↓
Encrypted secrets
        ↓
Prompt injection controls
        ↓
Sandbox isolation
        ↓
Network restrictions
        ↓
Audit logging
        ↓
Data deletion
```

Use security baselines aligned with NIST SSDF, OWASP ASVS, OWASP LLM guidance and OpenSSF practices.

---

# 41. Cost Architecture

Risk controls spend:

```text
LOW
→ small model
→ limited retrieval
→ minimal tools

MEDIUM
→ normal model
→ hybrid retrieval

HIGH
→ reasoning model
→ static analysis
→ targeted execution

CRITICAL
→ strongest available model
→ deep context
→ full evidence
→ escalation
```

Required optimizations:

- Prompt caching.
- Context caching.
- Agent routing.
- Incremental reviews.
- Retrieval reuse.
- Context slicing.
- Per-PR token ceiling.
- Daily spend ceiling.

---

# 42. Review Reproducibility

A review must be reproducible using:

```text
repository
+
head_sha
+
base_sha
+
review configuration version
+
agent version
+
prompt version
+
model/provider metadata
+
tool versions
+
retrieved context identifiers
```

The system must not claim bit-for-bit deterministic model output; reproducibility means reconstructing the same review inputs and verification artifacts.

---

# 43. Performance Targets

| Metric | Target |
|---|---:|
| Webhook → queued | < 10 sec |
| Standard review P50 | < 3 min |
| Standard review P95 | < 8 min |
| Deep/Critical review P95 | < 15 min |
| Webhook availability | 99.9% |
| Signup → first repo connected | < 5 min |

---

# 44. Scaling Strategy

### V1

```text
PostgreSQL + pgvector
Redis Streams
Stateless API
Horizontally scaled workers
```

### V2

Introduce Qdrant when:

```text
p95 retrieval > 300ms for 1 hour
OR
repository vectors > 5M
```

Workers scale on:

```text
queue depth
+
review latency
+
tenant concurrency
```

---

# 45. Deployment Architecture

```text
                       Internet
                          |
                          v
                 HTTPS Load Balancer
                          |
                          v
                   FastAPI Services
                          |
             +------------+------------+
             |                         |
             v                         v
      Redis Streams               PostgreSQL
             |
             v
       Review Workers
       /      |       \
      /       |        \
     v        v         v
 Sandbox   LLM Gateway  GitHub API
     |
     v
 Tests / Tools

All services
     |
     v
OpenTelemetry
```

Infrastructure:

- Docker.
- Terraform.
- Kubernetes where operationally justified.
- GitHub Actions CI/CD.

---

# 46. Deployment Environments

```text
development
    ↓
staging
    ↓
production
```

Production promotion requires:

- Tests passing.
- Security checks passing.
- Evaluation benchmark passing.
- Infrastructure validation passing.
- No unresolved critical vulnerabilities.

---

# 47. Evaluation Architecture

```text
Historical PR Dataset
        |
        +-- Known defects
        +-- Security cases
        +-- Human comments
        +-- Negative examples
        |
        v
      Benchmark
        |
        +--> Precision
        +--> Recall
        +--> False positives
        +--> Acceptance
        +--> Evidence verification
        +--> Latency
        +--> Cost
```

North-star metric:

```text
Human-accepted high-value findings
----------------------------------
Senior-review minutes consumed
```

---

# 48. Engineering Quality Gates

A release must satisfy:

- High/blocking evidence gate.
- SHA-pinned citations.
- Duplicate finding deduplication.
- Repository-rule awareness.
- Reproducibility from commit.
- Tenant-isolated sandbox.
- Secret-safe logging.
- Visible partial failure.
- Measurable review latency.
- Regression benchmark.

---

# 49. Data Lifecycle

```text
Repository connected
       ↓
Index created
       ↓
PR reviewed
       ↓
Evidence stored
       ↓
Audit recorded
       ↓
Retention window
       ↓
Deletion request
       ↓
Repository data purge
       ↓
Embedding purge
       ↓
Review memory purge
       ↓
Observability purge
       ↓
Deletion verification
```

No soft-delete-only implementation is sufficient for user-requested deletion.

---

# 50. ADR Summary

### ADR-001
Use GitHub App rather than personal tokens.

### ADR-002
Use PostgreSQL + pgvector first.

### ADR-003
Use code graph plus retrieval rather than embeddings alone.

### ADR-004
Require evidence before high-impact publication.

### ADR-005
Use specialized agents rather than one monolithic reviewer.

### ADR-006
Use risk-adaptive routing for token/cost efficiency.

### ADR-007
Keep humans as final merge authority.

### ADR-008
Treat repository content as untrusted input.

---

# 51. End-to-End Sequence

```text
Developer
   |
   | Open / update PR
   v
GitHub
   |
   | webhook
   v
Meridian Gateway
   |
   | verify + idempotency
   v
Redis
   |
   v
Orchestrator
   |
   +--> Intent
   +--> Risk
   +--> Change Localization
   +--> Repository Retrieval
   |
   v
Review Agents
   |
   v
Evidence Planner
   |
   +--> Semgrep
   +--> CodeQL
   +--> Sandbox
   +--> Tests
   |
   v
Evidence Verifier
   |
   v
Adjudicator
   |
   +--> Suppress
   |
   +--> Publish
   |
   +--> Escalate
   |
   v
GitHub
   |
   v
Senior Engineer
```

---

# 52. V1 Implementation Boundaries

## Phase 1 — Platform

- GitHub App.
- OAuth.
- FastAPI.
- PostgreSQL.
- Redis Streams.
- Basic GitHub review publishing.

## Phase 2 — Intelligence

- Tree-sitter.
- SCIP/LSP.
- Repository index.
- pgvector.
- Hybrid retrieval.

## Phase 3 — Review

- Intent.
- Risk.
- Specialized agents.
- Conditional routing.

## Phase 4 — Verification

- Semgrep.
- CodeQL.
- Sandbox.
- Targeted tests.
- Evidence gate.

## Phase 5 — Production

- BYOK/KMS.
- Tenant isolation.
- Audit.
- Observability.
- Cost controls.
- Evaluation benchmark.
- Reliability hardening.

---

# 53. Final System Contract

Meridian's system contract is:

```text
INPUT
GitHub PR + repository context

        ↓

UNDERSTAND
Intent + change + risk

        ↓

LOCATE
Symbols + dependencies + affected behavior

        ↓

RETRIEVE
Relevant code + tests + docs + history + rules

        ↓

REASON
Specialized review agents

        ↓

VERIFY
Semgrep + CodeQL + execution + tests

        ↓

ADJUDICATE
Evidence + risk + confidence + policy

        ↓

PUBLISH
Only validated findings

        ↓

ESCALATE
Only high-risk / uncertain decisions

        ↓

OUTPUT
A senior-level first-pass review
without requiring a senior to initiate it.
```

---

# 54. System Success Condition

The system is successful when:

```text
15 PRs
   ↓
15 automatic first-pass reviews
   ↓
Only meaningful findings reach seniors
   ↓
Senior review time decreases
   ↓
Developer feedback arrives sooner
   ↓
False-positive review noise remains low
```

The goal is not to replace engineering judgment.

The goal is to **scale senior engineering judgment by automating the investigation that precedes it.**
