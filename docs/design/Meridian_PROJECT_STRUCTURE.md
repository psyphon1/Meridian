# Meridian — Project Structure

**Product:** Meridian  
**Owner:** Chinmay Duse (psyphon1)  
**GitHub:** https://github.com/psyphon1  
**LinkedIn:** https://linkedin.com/in/chinmayduse  
**Architecture:** Modular monorepo  
**Status:** Production-oriented V1 structure

---

## 1. Repository Structure

```text
meridian/
├── apps/
│   ├── api/                         # FastAPI application
│   ├── worker/                      # Async review workers
│   ├── web/                         # Next.js dashboard
│   └── github-app/                  # GitHub App metadata/config
│
├── packages/
│   ├── agents/                      # Specialized review agents
│   ├── orchestration/               # LangGraph workflows
│   ├── code-intelligence/           # Tree-sitter + SCIP/LSP
│   ├── retrieval/                   # Hybrid retrieval + reranking
│   ├── evidence/                    # Evidence planner/verifier
│   ├── analyzers/                   # Semgrep + CodeQL adapters
│   ├── sandbox/                     # Isolated execution abstraction
│   ├── github/                      # GitHub API/client layer
│   ├── risk-engine/                 # Risk and escalation scoring
│   ├── models/                      # Shared domain schemas
│   ├── security/                    # Secrets, auth, isolation helpers
│   ├── observability/               # OpenTelemetry/Langfuse
│   └── config/                      # Shared configuration
│
├── services/
│   ├── repository-indexer/          # Initial + incremental repository indexing
│   ├── review-engine/               # Review execution service
│   ├── evidence-engine/             # Evidence verification service
│   ├── notification-service/        # Escalations and user notifications
│   └── audit-service/               # Append-only audit pipeline
│
├── infra/
│   ├── terraform/
│   │   ├── modules/
│   │   └── environments/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── production/
│   ├── kubernetes/
│   │   ├── base/
│   │   └── overlays/
│   ├── docker/
│   └── sandbox/
│
├── db/
│   ├── migrations/
│   ├── seeds/
│   └── schema/
│
├── docs/
│   ├── PRD.md
│   ├── SDD.md
│   ├── TRD.md
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── SECURITY.md
│   ├── COMPLIANCE.md
│   ├── AGENT_STANDARDS.md
│   ├── DEVELOPER_STANDARDS.md
│   ├── CODE_STANDARDS.md
│   ├── UI_UX.md
│   ├── SETUP.md
│   ├── DEPLOYMENT.md
│   ├── OBSERVABILITY.md
│   └── adr/
│
├── prompts/
│   ├── system/
│   ├── review/
│   ├── adjudication/
│   └── evidence/
│
├── evals/
│   ├── datasets/
│   ├── cases/
│   ├── graders/
│   ├── regression/
│   └── reports/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── e2e/
│   └── fixtures/
│
├── scripts/
│   ├── bootstrap/
│   ├── indexing/
│   ├── evaluation/
│   ├── migrations/
│   └── development/
│
├── .github/
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   ├── pull_request_template.md
│   └── dependabot.yml
│
├── .env.example
├── .gitignore
├── .dockerignore
├── Makefile
├── pyproject.toml
├── package.json
├── pnpm-workspace.yaml
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

# 2. Architecture Boundaries

```text
apps/
  = deployable applications

services/
  = independently scalable domain services

packages/
  = reusable libraries / domain capabilities

infra/
  = deployment and runtime infrastructure

db/
  = persistence schema and migrations

docs/
  = engineering contract

evals/
  = AI quality contract

tests/
  = software quality contract
```

A package must not reach into another package's internal implementation. Use public interfaces.

---

# 3. API Application

```text
apps/api/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── auth.py
│   │   │   ├── repositories.py
│   │   │   ├── reviews.py
│   │   │   ├── findings.py
│   │   │   ├── evidence.py
│   │   │   ├── keys.py
│   │   │   └── audit.py
│   │   └── dependencies.py
│   │
│   ├── webhooks/
│   │   ├── github.py
│   │   ├── verification.py
│   │   └── idempotency.py
│   │
│   ├── services/
│   ├── repositories/
│   ├── schemas/
│   ├── middleware/
│   └── config/
│
└── tests/
```

The API layer must remain thin. Business logic belongs in domain/service packages.

---

# 4. Worker Application

```text
apps/worker/
├── worker/
│   ├── main.py
│   ├── consumers/
│   │   ├── review_consumer.py
│   │   ├── indexing_consumer.py
│   │   └── audit_consumer.py
│   │
│   ├── schedulers/
│   │   └── sandbox_scheduler.py
│   │
│   ├── handlers/
│   └── config/
│
└── tests/
```

Workers must be stateless except for checkpointed workflow state and temporary execution artifacts.

---

# 5. Review Orchestration

```text
packages/orchestration/
├── graph/
│   ├── review_graph.py
│   ├── nodes/
│   │   ├── intent.py
│   │   ├── localization.py
│   │   ├── risk.py
│   │   ├── retrieval.py
│   │   ├── agent_router.py
│   │   ├── evidence_planner.py
│   │   ├── verification.py
│   │   ├── adjudication.py
│   │   ├── publishing.py
│   │   └── escalation.py
│   ├── state.py
│   └── checkpoints.py
│
├── policies/
├── routing/
└── tests/
```

The graph is the workflow controller; agents must not orchestrate themselves.

---

# 6. Agent Package

```text
packages/agents/
├── base/
│   ├── agent.py
│   ├── context.py
│   ├── output.py
│   └── errors.py
│
├── correctness/
├── security/
├── performance/
├── architecture/
├── reliability/
└── testing/
```

Each agent owns:

```text
prompt
input schema
output schema
tool policy
token budget
risk policy
evaluation cases
```

Agents produce hypotheses only.

---

# 7. Code Intelligence

```text
packages/code-intelligence/
├── parsers/
│   └── treesitter/
├── navigation/
│   ├── scip/
│   └── lsp/
├── graph/
│   ├── symbols.py
│   ├── calls.py
│   ├── imports.py
│   └── dependencies.py
├── localization/
└── tests/
```

Responsibilities:

- AST extraction.
- Symbol discovery.
- Definitions/references.
- Call graph.
- Dependency graph.
- Changed-symbol localization.

---

# 8. Repository Indexer

```text
services/repository-indexer/
├── discovery/
├── parsers/
├── graph-builder/
├── embeddings/
├── lexical-index/
├── historical-memory/
├── incremental/
├── debounce/
└── tests/
```

Pipeline:

```text
Repository
   ↓
File Discovery
   ↓
Tree-sitter
   ↓
SCIP/LSP
   ↓
Graph Construction
   ↓
Embeddings
   ↓
Lexical Index
   ↓
Historical Memory
   ↓
Persist
```

---

# 9. Retrieval Package

```text
packages/retrieval/
├── lexical/
│   └── bm25.py
├── semantic/
│   ├── embeddings.py
│   └── vector_store.py
├── graph/
│   └── graph_retriever.py
├── historical/
│   └── review_memory.py
├── tests/
├── fusion/
│   └── rrf.py
└── reranking/
    └── reranker.py
```

Retrieval strategy:

```text
BM25
Dense
Symbol / Graph
Historical
Tests
  ↓
Fusion
  ↓
Rerank
  ↓
Context Selection
```

---

# 10. Evidence Engine

```text
packages/evidence/
├── planner/
├── verifier/
├── schemas/
├── citations/
├── policies/
└── tests/
```

The evidence engine must distinguish:

```text
VERIFIED
UNVERIFIED
CONTRADICTED
PARTIAL
```

---

# 11. Analyzer Adapters

```text
packages/analyzers/
├── semgrep/
│   ├── client.py
│   ├── parser.py
│   └── policies.py
│
├── codeql/
│   ├── client.py
│   ├── parser.py
│   └── policies.py
│
└── common/
```

Adapters normalize tool output into Meridian's evidence schema.

---

# 12. Sandbox Package

```text
packages/sandbox/
├── interface.py
├── scheduler.py
├── runtime/
│   ├── docker.py
│   ├── firecracker.py
│   └── gvisor.py
├── policies/
│   ├── network.py
│   ├── resources.py
│   └── filesystem.py
├── artifacts/
└── tests/
```

The rest of Meridian must communicate with the sandbox through the abstraction rather than directly calling Docker/microVM APIs.

---

# 13. GitHub Package

```text
packages/github/
├── app/
│   ├── authentication.py
│   ├── installations.py
│   └── permissions.py
├── pull_requests/
├── reviews/
├── webhooks/
├── rate_limit/
├── links/
└── tests/
```

Responsibilities:

- GitHub API calls.
- Installation token management.
- PR retrieval.
- Review publishing.
- SHA-pinned links.
- Rate limiting.
- Retry/backoff.

---

# 14. Risk Engine

```text
packages/risk-engine/
├── features/
│   ├── pr_size.py
│   ├── change_type.py
│   ├── sensitivity.py
│   ├── blast_radius.py
│   ├── criticality.py
│   ├── history.py
│   └── uncertainty.py
├── scoring.py
├── routing.py
├── escalation.py
└── tests/
```

Output:

```text
risk_tier
model_tier
retrieval_budget
tool_budget
agent_selection
token_ceiling
escalation_policy
```

---

# 15. Evidence-Gated Publication

The publish path must be isolated:

```text
Agent Findings
     ↓
Evidence Planner
     ↓
Tool Execution
     ↓
Evidence Verifier
     ↓
Adjudicator
     ↓
Publish Policy
     |
     +--> SUPPRESS
     +--> DOWNGRADE
     +--> PUBLISH
     +--> ESCALATE
```

No agent should bypass this path.

---

# 16. Shared Domain Models

```text
packages/models/
├── user.py
├── installation.py
├── repository.py
├── pull_request.py
├── review_run.py
├── finding.py
├── evidence.py
├── tool_run.py
├── code_symbol.py
├── review_memory.py
├── audit_event.py
└── enums.py
```

Use versioned schemas for external/model-facing contracts.

---

# 17. Database Structure

```text
db/
├── migrations/
│   ├── 0001_initial.py
│   ├── 0002_repository.py
│   ├── 0003_review.py
│   └── ...
├── schema/
│   ├── users.sql
│   ├── repositories.sql
│   ├── reviews.sql
│   ├── findings.sql
│   └── audit.sql
└── seeds/
```

Database ownership belongs to the persistence layer. Domain packages should not embed raw SQL throughout business logic.

---

# 18. Security Package

```text
packages/security/
├── secrets/
│   ├── kms.py
│   └── rotation.py
├── auth/
├── tenant/
├── redaction/
├── prompt-injection/
├── policies/
└── tests/
```

Security controls must be reusable rather than reimplemented by individual services.

---

# 19. Observability

```text
packages/observability/
├── tracing/
├── metrics/
├── logging/
├── redaction/
├── cost/
└── evaluation/
```

Every request/review gets:

```text
trace_id
review_run_id
repository_id
tenant_id
```

Raw source code and secrets must not be logged.

---

# 20. Evaluation Structure

```text
evals/
├── datasets/
│   ├── historical/
│   ├── security/
│   ├── correctness/
│   ├── architecture/
│   └── negative/
│
├── graders/
├── cases/
├── regression/
├── experiments/
└── reports/
```

Every model/prompt/retrieval change should be evaluated before production release.

---

# 21. Prompt Structure

```text
prompts/
├── system/
│   ├── base.md
│   ├── security.md
│   └── evidence.md
├── review/
│   ├── correctness.md
│   ├── security.md
│   ├── performance.md
│   ├── architecture.md
│   ├── reliability.md
│   └── testing.md
├── adjudication/
└── evidence/
```

Prompts are version-controlled artifacts.

Never hard-code large prompts inside Python/TypeScript modules.

---

# 22. Frontend Structure

```text
apps/web/
├── app/
│   ├── (auth)/
│   ├── dashboard/
│   ├── repositories/
│   ├── reviews/
│   ├── settings/
│   └── api/
│
├── components/
│   ├── review/
│   ├── findings/
│   ├── evidence/
│   ├── repositories/
│   ├── onboarding/
│   └── common/
│
├── lib/
│   ├── api/
│   ├── auth/
│   └── realtime/
│
├── hooks/
├── types/
└── tests/
```

---

# 23. Documentation Structure

```text
docs/
├── PRD.md
├── SDD.md
├── TRD.md
├── ARCHITECTURE.md
├── PROJECT_STRUCTURE.md
├── SECURITY.md
├── COMPLIANCE.md
├── CODE_STANDARDS.md
├── DEVELOPER_STANDARDS.md
├── AGENT_STANDARDS.md
├── UI_UX.md
├── SETUP.md
├── DEPLOYMENT.md
├── OBSERVABILITY.md
└── adr/
    ├── ADR-001-github-app.md
    ├── ADR-002-postgres-pgvector.md
    ├── ADR-003-code-graph.md
    ├── ADR-004-evidence-gate.md
    ├── ADR-005-specialized-agents.md
    └── ADR-006-risk-adaptive-routing.md
```

---

# 24. Testing Pyramid

```text
                +---------+
                |   E2E   |
                +----+----+
                     |
              +------+------+
              | Integration |
              +------+------+
                     |
          +----------+----------+
          |        Unit         |
          +---------------------+
```

Additional AI-specific layers:

```text
Agent Evaluation
Retrieval Evaluation
Evidence Evaluation
Prompt Regression
Security Evaluation
```

---

# 25. Environment Separation

```text
.env.development
.env.test
.env.staging
.env.production
```

Secrets must never be committed.

Production secrets come from the managed secret/KMS system.

---

# 26. Ownership Rules

```text
apps/
  → application owners

packages/
  → capability owners

services/
  → service owners

infra/
  → infrastructure owner

docs/
  → architecture/product owner
```

CODEOWNERS should enforce review ownership for security-critical and infrastructure paths.

---

# 27. Dependency Rules

Allowed:

```text
apps → packages
services → packages
packages → lower-level packages
infra → deployment definitions
```

Avoid:

```text
package A → application internals
package A → package B internals
agent → database internals
agent → GitHub SDK directly
```

Use interfaces/adapters.

---

# 28. Recommended Local Development

```text
docker-compose
├── postgres
├── redis
├── api
├── worker
└── web
```

Optional local tools:

```text
Semgrep
CodeQL
Tree-sitter
SCIP indexer
sandbox runtime
```

---

# 29. Makefile Contract

```text
make setup
make dev
make api
make worker
make web

make test
make test-unit
make test-integration
make test-e2e

make lint
make format
make typecheck
make security

make index
make eval
make benchmark

make docker-build
make docker-up
make docker-down
```

---

# 30. Project-Level Rules

1. No business logic in controllers/routes.
2. No direct LLM calls inside domain agents without the model gateway.
3. No raw GitHub API calls outside the GitHub adapter.
4. No direct Docker/Firecracker calls outside the sandbox package.
5. No finding can bypass the evidence/adjudication pipeline.
6. No secret is allowed in logs or traces.
7. All external/model-facing schemas are versioned.
8. All critical behavior has automated tests.
9. Architecture changes require an ADR.
10. New agents require evaluation cases before production use.

---

# 31. Production Runtime Mapping

```text
GitHub
  ↓
apps/api
  ↓
Redis Streams
  ↓
apps/worker
  ↓
packages/orchestration
  ├── packages/risk-engine
  ├── packages/code-intelligence
  ├── packages/retrieval
  ├── packages/agents
  └── packages/evidence
          ↓
   analyzers + sandbox
          ↓
   GitHub publisher
          ↓
   escalation
```

---

# 32. Final Principle

The repository structure should make the architecture obvious.

A developer opening the repository should immediately understand:

```text
Where is the API?
Where is the workflow?
Where are the agents?
Where is code intelligence?
Where is retrieval?
Where is verification?
Where is the sandbox?
Where is the GitHub adapter?
Where is the database?
Where are evaluations?
Where are security controls?
Where are the deployment definitions?
```

If the answer requires reading unrelated application code, the structure is wrong.
