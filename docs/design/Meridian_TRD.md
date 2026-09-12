# Meridian — Autonomous AI PR Reviewer
# Technical Requirements Document (TRD)

**Product:** Meridian — Autonomous AI PR Reviewer  
**Owner:** Chinmay Duse (psyphon1)  
**GitHub:** https://github.com/psyphon1  
**LinkedIn:** https://linkedin.com/in/chinmayduse  
**Version:** 2.1  
**Status:** Final

## 1. Purpose

Meridian is a production-grade GitHub App that automatically performs the first-pass senior-level review of pull requests.

The system must receive PR events, build repository-aware context, localize changes, route relevant review agents, verify important findings, suppress unsupported claims, publish structured GitHub reviews, and escalate high-risk or uncertain findings to humans.

## 2. Core Principles

- **Context before judgment:** never evaluate a changed line without relevant repository context.
- **Evidence over opinion:** `BLOCKING` and `HIGH` findings require verifiable evidence.
- **Risk-adaptive depth:** compute and tool usage scale with risk.
- **Fewer, better comments:** optimize for accepted/actionable findings.
- **Human accountability:** Meridian assists; humans remain final merge authority.
- **Tenant isolation:** user data, keys and execution environments are isolated.
- **Token efficiency:** every retrieval, model call and tool call must justify its cost.

## 3. System Architecture

```text
GitHub PR
   |
   v
Webhook Gateway
   |
   +--> signature verification
   +--> idempotency
   |
   v
Redis Streams
   |
   v
LangGraph Orchestrator
   |
   +--> Intent + Risk
   +--> Change Localization
   +--> Repository Intelligence
   |       +--> Tree-sitter
   |       +--> SCIP/LSP
   |       +--> Git history
   |       +--> Docs / rules
   |       +--> Hybrid retrieval
   |
   v
Conditional Review Agents
   |
   +--> Correctness
   +--> Security
   +--> Performance
   +--> Architecture
   +--> Reliability
   +--> Testing
   |
   v
Evidence Engine
   |
   +--> Semgrep
   +--> CodeQL
   +--> Targeted tests
   +--> Data/control-flow inspection
   |
   v
Adjudication
   |
   +--> Confidence
   +--> Severity
   +--> Citation validation
   |
   +--> GitHub Review
   |
   +--> Human Escalation
```

## 4. Technology Stack

| Layer | Technology | Technical requirement |
|---|---|---|
| Frontend | Next.js + TypeScript | Dashboard, onboarding, review status, findings, configuration |
| Identity | GitHub OAuth App | Identity/session only |
| Repository access | GitHub App | Installation-scoped repository access and PR reviews |
| API | FastAPI | Webhooks and application API |
| Workflow | LangGraph | Stateful, checkpointed orchestration |
| Queue | Redis Streams | Durable async jobs with consumer groups |
| Parsing | Tree-sitter | Multi-language AST/syntax extraction |
| Code intelligence | SCIP/LSP | Definitions, references and relationships |
| Database | PostgreSQL | Canonical application state |
| Vector search | pgvector V1 | Repository/review embeddings |
| Vector scale-out | Qdrant V2 | Optional migration for hot/large repositories |
| Lexical search | PostgreSQL FTS/BM25-compatible | Exact symbol/identifier retrieval |
| Reranking | Cross-encoder/reranker | Context precision |
| Model gateway | LiteLLM | Provider abstraction and BYOK injection |
| Inference | Frontier APIs + vLLM | Hosted quality + optional self-hosted inference |
| Static analysis | Semgrep | Fast deterministic code/security checks |
| Semantic analysis | CodeQL | Deep data-flow/security verification |
| Execution | Isolated sandbox | Build, test and reproduction execution |
| Secrets | KMS / Vault | Envelope encryption |
| Observability | OpenTelemetry + Langfuse | Trace, latency, cost and evaluation |
| Infrastructure | Docker + Kubernetes + Terraform | Reproducible deployment |
| CI/CD | GitHub Actions | Build/test/security/deploy |

## 5. GitHub Integration

### GitHub App

Requirements:

- Installation-scoped access.
- Minimum permissions.
- Secure webhook secret.
- Signature verification.
- PR `opened` and `synchronize` handling.
- Review publishing.
- Installation/uninstallation lifecycle.
- Repository selection/configuration.

OAuth identity and repository authorization must remain separate.

### Webhook

```text
GitHub
  |
  v
Verify signature
  |
  v
Extract repository + PR + base_sha + head_sha
  |
  v
Idempotency check
  |
  v
Persist event
  |
  v
Enqueue review
  |
  v
Return quickly
```

Required idempotency key:

```text
repository_id + pr_number + head_sha
```

A database uniqueness constraint must prevent duplicate review creation.

## 6. API

Suggested endpoints:

```text
POST   /api/webhooks/github
GET    /api/me
GET    /api/repositories
PATCH  /api/repositories/{id}/config
GET    /api/reviews
GET    /api/reviews/{id}
GET    /api/reviews/{id}/findings
GET    /api/reviews/{id}/evidence
GET    /api/audit
POST   /api/keys
POST   /api/keys/{id}/rotate
DELETE /api/keys/{id}
POST   /api/data-deletion
```

API requirements:

- OpenAPI specification.
- Versioned contracts.
- Authentication.
- Request validation.
- Rate limiting.
- Correlation/review-run IDs.
- Consistent error envelopes.
- No secrets in errors/logs.

## 7. Repository Intelligence

Index and maintain:

- Files.
- Symbols.
- Definitions.
- References.
- Imports/dependencies.
- Call relationships.
- Test relationships.
- Docs.
- Configuration.
- Repository rules.
- Historical review memory.
- Embeddings.
- Sparse/BM25 index.

### Incremental indexing

Batch rapid repository changes using a **30–60 second debounce window** to avoid index thrashing.

Only changed files/symbols should be reprocessed where possible.

## 8. Code Intelligence

### Tree-sitter

Used for:

- AST extraction.
- Function/class/method boundaries.
- Incremental parsing.
- Multi-language support.

### SCIP/LSP

Used for:

- Definitions.
- References.
- Implementations.
- Call relationships.
- Symbol-aware context expansion.

**Design rule:** embeddings identify semantic relevance; code intelligence establishes structural relationships.

## 9. Retrieval

Use hybrid retrieval:

```text
              Query
                |
     +----------+----------+
     |          |          |
    BM25      Dense     Symbol/Graph
     |          |          |
     +----------+----------+
                |
       Historical Reviews
                |
          Test Retrieval
                |
              Fusion
                |
            Reranker
                |
        Context Selection
```

Priority:

1. Changed symbols.
2. Direct callers/callees.
3. Related tests.
4. Repository rules/docs.
5. Historical PR/review evidence.
6. Broader context only when uncertainty requires it.

V1 storage: PostgreSQL + pgvector partitioned by `repository_id`.

Move hot repositories to Qdrant when either:

```text
p95 retrieval latency > 300 ms for 1 hour
OR
repository vector count > 5M
```

## 10. Review Orchestration

```text
PR
 ↓
Intent Analysis
 ↓
Change Localization
 ↓
Risk Classification
 ↓
Context Retrieval
 ↓
Conditional Agents
 ↓
Evidence Planner
 ↓
Tool Execution
 ↓
Evidence Verifier
 ↓
Adjudication
 ↓
Severity + Confidence
 ↓
Citation Validation
 ↓
GitHub Review
 ↓
Human Escalation
```

LangGraph workflow state must be checkpointed after nodes so workers can resume without unnecessary LLM re-calls.

## 11. Review Agents

Required agents:

- Correctness.
- Security.
- Performance.
- Architecture.
- Reliability.
- Testing.

Agents produce **structured hypotheses**, never trusted final comments.

Required path:

```text
Agent
 ↓
Evidence Planner
 ↓
Tool Execution
 ↓
Verifier
 ↓
Adjudicator
 ↓
Publishable Finding
```

No agent may independently create and validate its own critical finding.

### Conditional routing

| Change | Agents |
|---|---|
| Docs-only | Skip review agents |
| Config-only | Reliability + Architecture |
| Standard code | Correctness + Test + Architecture |
| Auth/secrets/payment/database | Security deep mode |
| Hot-path performance | Performance |
| Concurrency/migration | Reliability deep mode |

## 12. Risk Engine

Risk considers:

```text
PR size
+ change type
+ subsystem touched
+ sensitivity
+ dependency blast radius
+ production criticality
+ historical defect density
+ uncertainty
```

Risk controls:

- Model tier.
- Retrieval budget.
- Agent selection.
- Tool execution.
- Evidence requirements.
- Escalation policy.
- Per-PR token ceiling.

## 13. Incremental Re-review

```text
New diff
  ↓
Changed symbols
  ↓
Affected dependency graph
  ↓
Reuse unchanged context
  ↓
Reuse prior findings
  ↓
Review impacted areas only
```

Unchanged symbols/files should incur zero additional review spend.

## 14. Evidence Verification

Evidence priority:

1. Reproduced failure.
2. Semgrep/CodeQL result.
3. Concrete control/data-flow trace.
4. Existing test evidence.
5. Strong repository-grounded reasoning.
6. Model intuition.

Model intuition alone can never justify a `BLOCKING` or `HIGH` finding.

### Publish gate

```text
IF severity IN (BLOCKING, HIGH):

  evidence_ref != NULL

  AND evidence_ref.type IN
      (tool_run, test_execution, sha_pinned_code_span)

  AND adjudicator re-derives claim from evidence artifact

ELSE:

  downgrade or suppress
```

The evidence gate must be enforced by application/schema logic, not only prompts.

## 15. Finding Schema

```json
{
  "agent_type": "security",
  "category": "authorization",
  "severity": "HIGH",
  "confidence": 0.94,
  "file": "src/auth/service.py",
  "line": 142,
  "claim": "Authorization can be bypassed",
  "evidence_ref": "evidence_123",
  "evidence_type": "tool_run",
  "verification_method": "codeql",
  "verification_result": "verified",
  "status": "publishable",
  "github_permalink": "..."
}
```

Every published finding must include:

- Severity.
- Confidence.
- Claim.
- File/line.
- Evidence.
- Verification result.
- Recommendation.
- SHA-pinned GitHub permalink.

## 16. Human Escalation

Escalation depends on:

```text
Risk
 ×
Confidence
 ×
Blast Radius
 ×
Repository Policy
```

Typical escalation cases:

- Critical security.
- High-impact database migrations.
- Large architectural changes.
- Low-confidence/high-impact findings.
- Unresolved tool contradictions.
- Repository-specific policies requiring human approval.

## 17. BYOK & Tenant Isolation

V1 model: **tenant = user**, no RBAC.

### Key handling

- TLS submission.
- Envelope encryption.
- User-scoped DEK wrapped by KMS-held KEK.
- Ciphertext only in persistence.
- Decrypt at LLM-call time.
- In-memory only.
- Never log keys.
- Rotation required.
- Multiple provider keys supported.

### Execution isolation

- Tenant-scoped execution boundary.
- Per-job isolated runtime.
- Ephemeral execution.
- Hard CPU/memory/time limits.
- Deny-all network egress by default.
- Explicit package-registry allowlist.
- Runtime destruction after execution.

Production architecture should support a stronger Firecracker/gVisor-style isolation path.

## 18. Prompt Injection Defense

Trust hierarchy:

```text
System policy
  >
Review policy
  >
Repository rules
  >
Repository content
  >
PR/user text
```

Requirements:

- Repository content never enters system/developer role.
- Explicit delimiters.
- Structured outputs.
- Tool allowlists.
- Tool-argument validation.
- Treat repository content as untrusted data.
- Do not allow repository content to alter system policy.

## 19. Sandbox

Sandbox must support:

- Build.
- Unit/integration tests.
- Targeted test execution.
- Reproduction.
- Generated regression tests.
- Static-analysis commands.

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

## 20. Queue

Use Redis Streams with consumer groups.

Requirements:

- Durable enqueue.
- Retry.
- Consumer recovery.
- Dead-letter queue.
- Tenant concurrency limits.
- Risk-aware priority.
- Queue observability.

A single tenant must not starve other tenants.

## 21. GitHub API Reliability

Implement:

- Per-installation rate limiting.
- Request coalescing.
- Exponential backoff.
- Secondary-rate-limit handling.
- Circuit breaker.
- Delayed queue state instead of dropped work.

## 22. Database Model

Core entities:

```text
User
APIKey
Installation
Repository
PullRequest
Commit
File
CodeSymbol
ReviewRun
Finding
Evidence
ToolRun
ReviewMemory
AuditLog
```

### User

```text
id
github_user_id
email
created_at
retention_policy_days
```

### APIKey

```text
id
user_id
provider
dek_ciphertext
kek_key_id
active
created_at
rotated_at
```

### Installation

```text
id
user_id
installation_id
github_org_or_user
status
created_at
```

### Repository

```text
id
installation_id
owner
name
default_branch
configuration
index_version
spend_cap_daily
created_at
updated_at
```

### PullRequest

```text
id
repository_id
number
head_sha
base_sha
intent
change_type
risk_score
status
token_spend
started_at
completed_at
```

### CodeSymbol

```text
id
repository_id
file_path
symbol_name
symbol_type
definition_location
references
embedding
```

### Finding

```text
id
pr_id
agent_type
category
severity
confidence
file
line
claim
evidence_ref
evidence_type
verification_method
verification_result
status
github_permalink
```

### ReviewMemory

```text
repository_id
source_type
source_reference
summary
embedding
created_at
```

### AuditLog

```text
id
user_id
event_type
target_resource
payload_redacted
prev_hash
row_hash
created_at
```

## 23. Audit & Compliance

Audit events include:

- Login.
- Key add/rotate/delete.
- GitHub install/uninstall.
- Repository connect/disconnect.
- Review start/status/finish.
- Finding publication.
- Configuration changes.
- Data export.
- Data deletion request.

Audit requirements:

- Append-only.
- Hash-chained.
- Separate from operational data.
- Redacted.
- Queryable.

Data retention must be configurable within policy limits, with verified cascading deletion.

Baseline engineering alignment:

- NIST SSDF.
- OWASP ASVS.
- OWASP LLM security guidance.
- OpenSSF supply-chain practices.
- OpenTelemetry semantic conventions.

These are engineering baselines, not certification claims.

## 24. Security Requirements

Mandatory:

- Minimum GitHub permissions.
- Webhook signature verification.
- TLS.
- Encrypted secrets.
- No keys/raw repository content in logs.
- Redacted observability.
- Tenant isolation.
- Sandboxed execution.
- Network egress restrictions.
- Audit logging.
- Dependency/security scanning.
- Secret scanning.
- SBOM generation.
- Data deletion workflow.

## 25. Reliability & SLA Targets

| Metric | Target |
|---|---:|
| Webhook → queued | < 10 sec |
| Standard review P50 | < 3 min |
| Standard review P95 | < 8 min |
| Deep/Critical review P95 | < 15 min |
| Webhook availability | 99.9% |
| Signup → first repo connected | < 5 min |

Reliability requirements:

- DB-level idempotency.
- Bounded retries.
- Workflow checkpointing.
- Explicit `PARTIAL_REVIEW`.
- Visible queue/sandbox exhaustion.
- GitHub API backoff/circuit breaker.

## 26. Cost & Token Efficiency

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
→ full verification
→ escalation
```

Controls:

- Prompt/context caching.
- Conditional agent routing.
- Incremental re-review.
- Context slicing.
- Per-PR token ceilings.
- Daily spend ceilings.
- CRITICAL pre-flight estimates.

## 27. Observability

Trace:

```text
Webhook
 → Intent
 → Localization
 → Retrieval
 → Agents
 → Tools
 → Sandbox
 → Adjudication
 → Publish
```

Track:

- Latency by stage.
- Tokens.
- Retrieval quality.
- Tool time.
- Retries.
- Evidence rate.
- False positives.
- Accepted/rejected findings.
- Cost/PR.
- Escalation rate.
- Queue depth.

Raw repository content, secrets and API keys must not enter shared telemetry.

## 28. Testing

### Unit

- Risk calculation.
- Evidence gate.
- Severity policy.
- Retrieval selection.
- Idempotency.
- Tenant isolation.
- Key lifecycle.

### Integration

- GitHub webhook.
- Database.
- Redis.
- GitHub review publishing.
- Semgrep/CodeQL.
- Sandbox.
- LLM gateway.

### Security

- Prompt injection.
- Secret leakage.
- Cross-tenant access.
- Sandbox security.
- SSRF/network egress.
- Dependency vulnerabilities.

### End-to-end

```text
PR
→ webhook
→ queue
→ context
→ agents
→ verification
→ adjudication
→ GitHub review
```

## 29. CI/CD

```text
PR
 ↓
Lint
 ↓
Typecheck
 ↓
Unit Tests
 ↓
Integration Tests
 ↓
Security/Dependency Scan
 ↓
Build
 ↓
Artifact Validation
 ↓
Deploy
```

Production deployment requires all mandatory checks.

## 30. Infrastructure

Required environments:

```text
development
staging
production
```

Terraform manages production infrastructure.

Production should provide:

- HTTPS.
- Managed PostgreSQL.
- Redis Streams.
- KMS/secret manager.
- Worker autoscaling.
- Isolated sandbox.
- Observability.
- Backup/recovery.
- Audit storage.

## 31. Evaluation

Maintain a versioned benchmark containing:

- Historical PRs.
- Human review comments.
- Seeded defects.
- Security cases.
- Architecture regressions.
- Negative examples.

Metrics:

- Precision.
- Recall.
- False-positive rate.
- Human acceptance rate.
- Review latency.
- Escalation rate.
- Citation-verifiable rate.
- Cost/PR.

### North-star

```text
Human-accepted high-value findings
----------------------------------
Senior-review minutes consumed
```

## 32. Quality Gates

V1 must satisfy:

- No blocking/high finding without evidence.
- Every published finding has a SHA-pinned citation.
- Duplicate findings are deduplicated.
- Review is reproducible from commit SHA.
- Repository rules affect review.
- Security-sensitive PRs trigger deeper checks.
- Sandbox is tenant isolated.
- Partial failures are visible.
- Latency is observable.
- User keys never enter logs/traces/exports.
- Data deletion is verifiable.

## 33. Recommended Implementation Order

```text
Phase 1
GitHub App + FastAPI + PostgreSQL + Redis
        ↓
Phase 2
LangGraph review workflow + basic LLM review
        ↓
Phase 3
Tree-sitter + SCIP/LSP + repository indexing
        ↓
Phase 4
Hybrid retrieval + historical context
        ↓
Phase 5
Specialized agents + risk routing
        ↓
Phase 6
Semgrep + CodeQL + sandbox verification
        ↓
Phase 7
Evidence gate + citations + escalation
        ↓
Phase 8
Observability + audit + cost controls
        ↓
Phase 9
Production hardening + benchmark
```

## 34. Technical Definition of Done

Meridian is technically ready for V1 when:

- GitHub events are signature-verified.
- Duplicate events are idempotent.
- Repository intelligence is incremental.
- Symbols/references are available.
- Hybrid retrieval works.
- Agents are conditionally routed.
- High-impact findings require evidence.
- Findings contain SHA-pinned citations.
- Sandbox execution is isolated.
- User keys are encrypted and never logged.
- Workflow state survives worker failure.
- Partial failure is explicit.
- Audit events are recorded.
- Cost and latency are measurable.
- Regression benchmark passes.

## 35. Technical North Star

```text
LLM
 = reasoning

Tree-sitter + SCIP/LSP
 = structural truth

Semgrep + CodeQL + sandbox tests
 = evidence

PostgreSQL
 = source of truth

LangGraph
 = orchestration

GitHub App
 = integration boundary

Human engineer
 = final authority
```
