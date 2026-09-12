# Meridian — Architecture Document

**Product:** Meridian  
**Owner:** Chinmay Duse (psyphon1)  
**GitHub:** https://github.com/psyphon1  
**LinkedIn:** https://linkedin.com/in/chinmayduse  
**Version:** 2.0  
**Status:** Final

---

## 1. Architecture Overview

Meridian is an autonomous GitHub PR-review platform that performs the first senior-level review automatically after a PR is opened or updated.

The architectural goal is to separate:

```text
Reasoning
  +
Code intelligence
  +
Retrieval
  +
Deterministic verification
  +
Execution isolation
  +
Policy
  +
Human escalation
```

The LLM is not the source of truth. It is a reasoning component inside a larger evidence-driven system.

---

## 2. System Context

```text
                         +----------------------+
                         |      Developer       |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |       GitHub         |
                         |   Pull Request      |
                         +----------+-----------+
                                    |
                             Webhook event
                                    |
                                    v
+----------------------------------------------------------------+
|                         MERIDIAN                               |
|                                                                |
|  +-------------+     +------------------+                      |
|  | Web/API     | --> | Review Workflow  |                      |
|  | Control     |     | Orchestrator     |                      |
|  +-------------+     +--------+---------+                      |
|                              |                                  |
|          +-------------------+-------------------+              |
|          |                   |                   |              |
|          v                   v                   v              |
|  Repository Intel       Risk Engine       Model Gateway        |
|          |                   |                   |              |
|          v                   v                   v              |
|  Context / Retrieval    Review Strategy     LLM Providers      |
|          |                   |                                  |
|          +-------------------+------------------+              |
|                              v                                  |
|                       Review Agents                             |
|                              |                                  |
|                              v                                  |
|                      Evidence Engine                            |
|                     /        |         \                         |
|                    v         v          v                        |
|                 Semgrep   CodeQL     Sandbox                     |
|                                      /     \                     |
|                                   Tests   Reproduction           |
|                              |                                  |
|                              v                                  |
|                       Adjudication                              |
|                         /       \                                |
|                        v         v                               |
|                  GitHub Review  Human Escalation                 |
+----------------------------------------------------------------+
```

---

# 3. Architectural Layers

## Layer 1 — Experience / Control Plane

```text
Next.js Dashboard
       |
       v
FastAPI
       |
       +--> Authentication
       +--> Repository configuration
       +--> BYOK management
       +--> Review status
       +--> Findings
       +--> Evidence
       +--> Spend
       +--> Audit
```

## Layer 2 — Integration

```text
GitHub App
  |
  +--> Webhooks
  +--> Installation auth
  +--> Repository access
  +--> Pull request data
  +--> Review publishing
```

## Layer 3 — Workflow

```text
Redis Streams
      |
      v
LangGraph
      |
      +--> intent
      +--> localization
      +--> risk
      +--> retrieval
      +--> agents
      +--> verification
      +--> adjudication
      +--> publishing
      +--> escalation
```

## Layer 4 — Intelligence

```text
Tree-sitter
SCIP/LSP
Hybrid Retrieval
Historical Memory
Review Agents
Risk Engine
```

## Layer 5 — Verification

```text
Semgrep
CodeQL
Sandbox
Targeted Tests
Evidence Verifier
```

## Layer 6 — Persistence / Governance

```text
PostgreSQL
pgvector
KMS/Vault
Audit Store
OpenTelemetry/Langfuse
```

---

# 4. Core Architecture

```text
                         GitHub
                           |
                           v
                  +------------------+
                  | Webhook Gateway  |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Redis Streams    |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | LangGraph        |
                  | Orchestrator     |
                  +--------+---------+
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
        Risk Engine   Repo Intelligence  Intent
                           |
              +------------+------------+
              |            |            |
              v            v            v
        Tree-sitter     SCIP/LSP     Retrieval
              |            |            |
              +------------+------------+
                           |
                           v
                  +------------------+
                  | Review Agents    |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Evidence Planner |
                  +--------+---------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
       Semgrep          CodeQL           Sandbox
                                           |
                                           v
                                      Targeted Tests
          +----------------+----------------+
                           |
                           v
                  +------------------+
                  | Evidence Verifier|
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Adjudicator       |
                  +--------+---------+
                           |
                 +---------+---------+
                 |                   |
                 v                   v
          GitHub Review       Human Escalation
```

---

# 5. Repository Intelligence Architecture

Repository intelligence is persistent and incremental.

```text
Repository
   |
   +--> File Index
   |
   +--> Tree-sitter
   |       |
   |       +--> AST
   |       +--> Symbols
   |
   +--> SCIP/LSP
   |       |
   |       +--> Definitions
   |       +--> References
   |       +--> Call graph
   |       +--> Dependencies
   |
   +--> Tests
   |
   +--> Docs / Config
   |
   +--> Git History
   |
   +--> Historical Reviews
   |
   +--> Embeddings / Lexical Index
```

Output:

```text
Repository Context Graph
```

This graph is reused across PRs.

---

# 6. Context Retrieval Architecture

```text
Changed Symbols
      |
      v
+-----+-----+---------+-------------+
|           |         |             |
v           v         v             v
BM25      Dense     Graph       Historical
Search    Search   Retrieval    Retrieval
|           |         |             |
+-----------+---------+-------------+
                    |
                    v
                  Fusion
                    |
                    v
                Reranker
                    |
                    v
              Context Selector
                    |
                    v
             Agent-specific
                  context
```

Retrieval is adaptive. The system expands context only when the current evidence is insufficient.

---

# 7. PR Change Graph

Every PR is converted into a change graph:

```text
PR
 |
 +--> changed files
       |
       +--> changed symbols
              |
              +--> callers
              +--> callees
              +--> imports
              +--> dependent modules
              +--> tests
              +--> APIs
              +--> database objects
```

This graph drives both retrieval and risk assessment.

---

# 8. Risk-Adaptive Architecture

```text
                 PR
                  |
                  v
            Risk Classifier
                  |
      +-----------+-----------+-----------+
      |           |           |           |
      v           v           v           v
     LOW       MEDIUM       HIGH       CRITICAL
      |           |           |           |
  Lite review  Normal     Deep review   Full review
      |           |           |           |
 Small model  Standard    Strong model  Strongest
 few tools    retrieval   + tools       + full verify
```

Risk considers:

```text
PR size
change type
subsystem
sensitivity
blast radius
production criticality
history
uncertainty
```

---

# 9. Multi-Agent Architecture

Agents are specialists, not autonomous system controllers.

```text
                     Review Context
                           |
                           v
                   Agent Router
            +------+------+------+------+------+
            |      |      |      |      |      |
            v      v      v      v      v      v
        Correct  Security Perf Architecture Reliability Test
            |      |      |      |      |      |
            +------+------+------+------+------+
                           |
                           v
                    Candidate Findings
```

Agents never publish directly.

---

# 10. Evidence Architecture

```text
Candidate Finding
       |
       v
Evidence Planner
       |
       +--> static analysis
       +--> data-flow analysis
       +--> repository inspection
       +--> targeted test
       +--> reproduction
       |
       v
Evidence Artifacts
       |
       v
Evidence Verifier
       |
  +----+----+----+
  |         |    |
  v         v    v
Verified  Partial  Contradicted
  |
  v
Adjudicator
```

Evidence priority:

```text
1. Reproduced failure
2. Semgrep / CodeQL
3. Concrete control/data flow
4. Existing test evidence
5. Strong repository reasoning
6. Model intuition
```

---

# 11. Evidence-Gated Publish Architecture

```text
Finding
   |
   v
Severity
   |
   +--> LOW/MEDIUM
   |       |
   |       v
   |    Publish policy
   |
   +--> HIGH/BLOCKING
           |
           v
      Evidence required
           |
      +----+----+
      |         |
    valid     invalid
      |         |
      v         v
   Publish   Suppress /
             downgrade
```

A high-impact comment cannot bypass the evidence gate.

---

# 12. Tenant Architecture

V1 uses:

```text
One User = One Tenant
```

Tenant boundary:

```text
User
 |
 +--> GitHub Installation
 +--> Repositories
 +--> Model Keys
 +--> Review Data
 +--> Embeddings
 +--> Sandbox
 +--> Audit Data
```

No cross-tenant data access is permitted.

---

# 13. Secret Architecture

```text
User
 |
 | TLS
 v
API
 |
 v
KMS / Vault
 |
 +--> encrypted key
 |
 v
PostgreSQL
```

Runtime:

```text
Encrypted Key
      |
      v
Decrypt in worker memory
      |
      v
LiteLLM request
      |
      v
Discard / zeroize
```

Keys must never enter logs, traces, prompts, GitHub comments or source control.

---

# 14. Execution Isolation

```text
Review Worker
     |
     v
Sandbox Scheduler
     |
     v
+-----------------------------+
| Tenant-isolated runtime     |
|                             |
| Repository snapshot         |
| Static analysis             |
| Build                       |
| Tests                       |
| Reproduction                |
+--------------+--------------+
               |
               v
          Evidence artifact
```

Required protections:

```text
CPU limits
memory limits
timeout
process limits
filesystem isolation
deny-all network
explicit package registry access
ephemeral runtime
```

---

# 15. Prompt Injection Boundary

Repository content is untrusted.

```text
                 TRUST
                   |
                   v
System Policy
      >
Review Policy
      >
Repository Rules
      >
Repository Content
      >
PR/User Text
```

Implementation:

- Repository text never becomes system/developer instructions.
- Structured agent outputs.
- Allowlisted tools.
- Validated tool arguments.
- No unrestricted shell.
- No repository content can modify system policy.

---

# 16. Persistence Architecture

```text
                 PostgreSQL
                     |
      +--------------+---------------+
      |              |               |
      v              v               v
 Application      Review State    Review Memory
    Data                               |
                                      v
                                   pgvector
```

Core data:

```text
Users
Installations
Repositories
PullRequests
Files
Symbols
ReviewRuns
Findings
Evidence
ToolRuns
ReviewMemory
AuditEvents
```

PostgreSQL remains the canonical source of truth.

---

# 17. Audit Architecture

```text
Application Events
        |
        v
Audit Service
        |
        v
Append-only Store
        |
        +--> previous hash
        +--> current hash
        +--> event payload
        +--> timestamp
```

This makes tampering detectable.

Audit data is kept logically separate from mutable operational state.

---

# 18. Queue Architecture

```text
                   Redis Streams
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Worker A       Worker B       Worker C
          |              |              |
          +--------------+--------------+
                         |
                         v
                  Review execution
```

Use:

- Consumer groups.
- Retry.
- Dead-letter queue.
- Tenant concurrency caps.
- Risk-aware priority.
- Durable job state.

---

# 19. GitHub API Reliability

```text
GitHub Request
      |
      v
Rate Limiter
      |
      +--> success --> continue
      |
      +--> limited
              |
              v
          backoff
              |
              v
          retry queue
              |
              v
        circuit breaker
```

The system must degrade to a delayed queue rather than silently dropping reviews.

---

# 20. Incremental Re-review

```text
Existing Review
      |
      v
New PR Push
      |
      v
New Diff
      |
      v
Changed Symbols
      |
      v
Affected Graph
      |
      v
Reuse:
  context
  evidence
  findings
      |
      v
Review only impacted areas
```

Goal:

```text
No additional spend for untouched code
```

where technically safe.

---

# 21. Dashboard Architecture

```text
                    Dashboard
                        |
        +---------------+----------------+
        |               |                |
        v               v                v
   Repositories      Reviews          Settings
                        |
                        v
                 Review Detail
                        |
              +---------+---------+
              |         |         |
              v         v         v
           Findings   Evidence   Context
```

The dashboard is the control plane, while GitHub remains the primary developer review surface.

---

# 22. Observability Architecture

```text
API
Workers
Agents
Retrieval
Tools
Sandbox
   |
   v
OpenTelemetry
   |
   v
Collector
   |
   +--> Metrics
   +--> Traces
   +--> Logs
   |
   v
Langfuse / observability backend
```

Trace attributes should include:

```text
tenant_id
repository_id
review_run_id
stage
agent
tool
model
latency
tokens
cost
result
```

No raw source code or secrets.

---

# 23. Deployment Architecture

```text
                    Internet
                       |
                       v
                Load Balancer
                       |
                       v
                  FastAPI API
                       |
             +---------+---------+
             |                   |
             v                   v
       Redis Streams         PostgreSQL
             |
             v
        Review Workers
       /      |       \
      v       v        v
   Sandbox  LLM       GitHub
             |
             v
       Model Providers
```

Infrastructure:

```text
Docker
Terraform
Kubernetes where justified
GitHub Actions
Managed PostgreSQL
Redis
KMS/Vault
```

---

# 24. Availability & Failure Model

```text
Webhook failure
   → retry

Worker failure
   → checkpoint resume

LLM failure
   → bounded retry / alternate configured provider

Tool failure
   → partial verification

Sandbox unavailable
   → queued / PARTIAL_REVIEW

GitHub rate limit
   → delayed queue

Evidence unavailable
   → suppress/downgrade

Spend limit reached
   → stop + notify
```

The system must never silently report a complete review when required analysis failed.

---

# 25. Architectural Quality Attributes

## Correctness

Evidence-gated publication and reproducible reviews.

## Security

Tenant isolation, secret protection, sandboxing and least privilege.

## Reliability

Durable queues, checkpoints, retries and idempotency.

## Performance

Incremental indexing, adaptive retrieval and risk-based compute.

## Scalability

Stateless API, horizontally scalable workers and tenant-aware scheduling.

## Maintainability

Clear adapters, domain boundaries and versioned schemas.

## Observability

End-to-end review tracing and measurable AI quality.

## Cost efficiency

BYOK, caching, conditional agents and incremental reviews.

---

# 26. Technology-to-Responsibility Mapping

```text
Next.js
→ user experience

FastAPI
→ API/control plane

GitHub App
→ repository boundary

Redis Streams
→ asynchronous execution

LangGraph
→ workflow orchestration

Tree-sitter
→ syntax/AST

SCIP/LSP
→ structural relationships

PostgreSQL
→ source of truth

pgvector
→ V1 semantic retrieval

Qdrant
→ V2 retrieval scale-out

BM25
→ exact lexical retrieval

Reranker
→ context precision

LiteLLM
→ model gateway

vLLM
→ self-hosted inference

Semgrep
→ fast deterministic analysis

CodeQL
→ deep semantic/data-flow analysis

Sandbox
→ executable evidence

OpenTelemetry
→ platform observability

Langfuse
→ AI workflow visibility/evaluation

Terraform
→ infrastructure definition
```

---

# 27. Architectural Decision Summary

### Decision 1 — GitHub App

Repository access must use a GitHub App rather than developer personal tokens.

### Decision 2 — PostgreSQL first

PostgreSQL + pgvector is the V1 canonical data/retrieval layer.

### Decision 3 — Graph + retrieval

Semantic retrieval is complemented by AST and symbol relationships.

### Decision 4 — Specialized agents

Review responsibilities are divided by engineering concern.

### Decision 5 — Evidence gate

Critical findings cannot be published from model intuition alone.

### Decision 6 — Adaptive depth

Compute grows with risk instead of PR size alone.

### Decision 7 — Human escalation

Humans retain final authority over high-impact decisions.

### Decision 8 — Untrusted repository

Repository files and PR text are data, not trusted instructions.

---

# 28. Final Architecture

```text
                         MERIDIAN
                            |
                            v
                      GitHub PR Event
                            |
                            v
                   +------------------+
                   | Webhook Gateway  |
                   +--------+---------+
                            |
                            v
                   +------------------+
                   | Redis Streams    |
                   +--------+---------+
                            |
                            v
                   +------------------+
                   | LangGraph        |
                   | Orchestrator     |
                   +--------+---------+
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
     Intent/Risk      Repository Intel      Policy
                          |
                 +--------+--------+
                 |        |       |
                 v        v       v
              AST      SCIP    Retrieval
                 \        |       /
                  +-------+------+
                          |
                          v
                   Review Agents
                          |
                          v
                  Evidence Planner
                          |
             +------------+------------+
             |            |            |
             v            v            v
          Semgrep      CodeQL       Sandbox
                                      |
                                      v
                                    Tests
             +------------+------------+
                          |
                          v
                  Evidence Verifier
                          |
                          v
                    Adjudicator
                          |
               +----------+----------+
               |                     |
               v                     v
        GitHub Review          Human Escalation
               |
               v
       Developer feedback

Supporting systems:
PostgreSQL + pgvector
KMS/Vault
OpenTelemetry + Langfuse
Terraform + Docker + Kubernetes
```

---

## 29. Architectural North Star

Meridian should behave like:

```text
A senior engineer's investigation process
          +
A static-analysis platform
          +
A repository intelligence engine
          +
A secure execution environment
          +
A GitHub-native workflow
```

The resulting system does not merely generate PR comments.

It **builds context → reasons → gathers evidence → verifies → decides → publishes → escalates**.
