# Meridian — Autonomous AI PR Reviewer

> **Your autonomous first-pass senior engineer for every GitHub pull request.**

<p align="center">
  <a href="https://github.com/psyphon1/Meridian/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/psyphon1/Meridian/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="Node 20+" src="https://img.shields.io/badge/node-20%2B-339933?logo=nodedotjs&logoColor=white">
  <img alt="TypeScript strict" src="https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white">
  <img alt="Status: Pre-Alpha" src="https://img.shields.io/badge/status-pre--alpha-orange">
  <img alt="Conventional Commits 1.0.0" src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg">
</p>

**Meridian** is an autonomous, evidence-driven AI code reviewer. For every GitHub pull request it performs the first senior-level investigation automatically — gathering repository-wide context, reasoning with specialized agents, and verifying claims with deterministic tools — then publishes an evidence-backed review with SHA-pinned citations and escalates only the decisions that still require human judgment.

> **Owner:** Chinmay Duse ([psyphon1](https://github.com/psyphon1)) · [LinkedIn](https://linkedin.com/in/chinmayduse)

---

## The problem it solves

Every team hits the same bottleneck: first-pass review queues behind a small number of senior engineers. In a team of 8, PRs wait **~4.2 hours** for a first review (GitHub Octoverse median), seniors spend **30–45 minutes per PR** on repetitive boilerplate before reaching the interesting architectural questions, and **40% of review comments** are stylistic or repetitive — things static analysis already caught.

Meridian removes that bottleneck by being the always-on first-pass senior engineer: it investigates context, reasons about correctness, verifies with deterministic tools, and posts evidence-backed findings the moment a PR opens — so humans review only what Meridian escalates or what genuinely requires judgment beyond pattern matching.

## What it does

- **Autonomous first-pass review** — every eligible PR is reviewed on open/update. No "ask permission" step, no manual trigger.
- **Repository-aware reasoning** — never evaluates a changed line without context: symbol definitions, call graphs, architecture rules, and historical review memory (Tree-sitter + SCIP/LSP).
- **Specialized review agents** — Correctness, Security (OWASP ASVS-mapped), Performance, Architecture, Reliability, and Testing — dispatched conditionally by risk.
- **Evidence-backed findings** — `BLOCKING` and `HIGH` findings require verifiable evidence (tool run, test execution, or a SHA-pinned code span), schema-enforced by an adjudicator.
- **SHA-pinned citations** — every comment links to exact lines at the exact commit (`github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}`).
- **Risk-adaptive compute** — a 2-line typo fix gets a light pass; a 500-line auth refactor gets deep verification. Minimum tokens per risk tier.
- **Human escalation** — high-risk, ambiguous, or novel findings escalate with full context. Meridian never guesses when stakes are high.
- **BYOK + tenant isolation** — users bring their own LLM keys, envelope-encrypted at rest and decrypted only in isolated worker memory. Strict per-tenant isolation; no cross-tenant data sharing.
- **Full auditability** — a tamper-evident, hash-chained audit log records every user and system action.
- **Observability first** — Google SRE golden signals over OpenTelemetry, with Langfuse for LLM-specific tracing (redacted before export).

## How it works

```
PR opened/updated
  → webhook (HMAC-verified, idempotent, <10s ack)
  → durable queue (Redis Streams, priority lanes)
  → intent + risk classification (risk-adaptive depth)
  → repository-aware retrieval (symbols, call graph, rules, review memory)
  → conditional specialized review agents (6 domains)
  → evidence verification (Semgrep / CodeQL / sandbox / tests)
  → adjudication (schema-enforced evidence gate)
  → GitHub review with SHA-pinned citations  |  OR  → human escalation
```

Agents produce **hypotheses**, never final comments. The adjudicator and deterministic verifiers decide what is published — no agent both invents and confirms its own claim.

## Core design principles

1. **The LLM is not the source of truth.** It is one reasoning component inside an evidence-driven system; deterministic tools and re-derivable evidence are the authority.
2. **The evidence gate is absolute.** No `BLOCKING`/`HIGH` finding publishes without a non-null `evidence_ref` that the adjudicator re-derives from the artifact (ADR-004).
3. **Trust hierarchy.** `System Policy > Review Policy > Repo Rules > Repo Content > PR Text` — repository content and PR text are untrusted data, never instructions.
4. **Separation of concerns.** LLM = reasoning · Tree-sitter/SCIP-LSP = structure · Semgrep/CodeQL = deterministic truth · sandbox = execution proof · PostgreSQL = source of truth · human = final authority.
5. **Human authority is final.** Meridian escalates; it never merges and never auto-applies fixes.
6. **Auditability and reproducibility.** A hash-chained audit log records everything, and any review is reproducible from a commit SHA.

## Technology stack

| Layer | Technology | Role |
|---|---|---|
| Dashboard | Next.js + TypeScript (strict) | Onboarding, live review status, cost meter |
| Identity | GitHub OAuth App | Session / sign-in only (separate from the App) |
| Repo access | GitHub App | Installation-scoped access, webhooks, review publish |
| API | FastAPI | Async webhooks + dashboard API, OpenAPI, versioned |
| Orchestration | LangGraph | Checkpointed after every node; resumable by stateless workers |
| Queue | Redis Streams | Consumer groups, per-tenant priority lanes |
| Code intelligence | Tree-sitter · SCIP/LSP | AST extraction · definitions/references |
| Database | PostgreSQL 16 + pgvector | System of record; partitioned by tenant/repo |
| Retrieval | pgvector + PG FTS/BM25 + reranker | Hybrid semantic + lexical |
| LLM gateway | LiteLLM | Per-request BYOK key injection |
| Static analysis | Semgrep · CodeQL | Deterministic + deep data-flow evidence |
| Execution | Firecracker / gVisor | Per-tenant isolated, pre-warmed, deny-all egress |
| Secrets | AWS/GCP KMS or Vault | Envelope-encrypted user keys |
| Observability | OpenTelemetry + Langfuse + structlog | Golden signals + LLM tracing (redacted) |
| Infra | Docker · Kubernetes · Terraform · GitHub Actions | Reproducible, digest-pinned deploys |

Full rationale for every choice — with syntax examples, system-design reasoning, and scaling discussion — lives in [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md).

## Repository structure

```
meridian/
├── apps/            # Deployable apps: api (FastAPI), worker, web (Next.js), github-app
├── packages/        # Capabilities: agents, orchestration, code-intelligence, retrieval,
│                    # evidence, analyzers, sandbox, github, risk-engine, models,
│                    # security, observability, config
├── services/        # repository-indexer, review-engine, evidence-engine,
│                    # notification-service, audit-service
├── infra/           # terraform (modules + dev/staging/prod), kubernetes (base+overlays),
│                    # docker, sandbox
├── db/              # migrations, seeds, schema
├── docs/            # This documentation set + design/ + adr/
├── prompts/         # system, review, evidence, adjudication (version-controlled)
├── evals/           # datasets, cases, graders, regression, reports
├── tests/           # unit, integration, security, e2e, fixtures
├── scripts/         # bootstrap, indexing, evaluation, migrations, development
└── .github/         # workflows (CI), ISSUE_TEMPLATE, PR template, dependabot, CODEOWNERS
```

Guiding rule: the structure must make the architecture obvious. If locating the API, workflow, agents, retrieval, or verification requires reading unrelated code, the structure is wrong.

### Dependency rules

**Allowed:** `apps → packages`, `services → packages`, `packages → lower-level packages`, `infra → deployment definitions`.
**Forbidden:** package → another package's internals · agent → database internals · agent → GitHub SDK directly · business logic in routes · raw LLM calls outside the model gateway · raw GitHub API calls outside the GitHub adapter · Docker/Firecracker calls outside the sandbox package.

## Getting started

> **Status: Pre-Alpha.** Design, documentation, scaffolding, and CI are complete and pushed; Phase 1 implementation is next. Backing services and the smoke-test suite run today — full app services follow as code lands (see [Status & roadmap](#status--roadmap)).

### Prerequisites

- **Python 3.12+** · **Node 20+ LTS** · **pnpm 9** · **Docker Desktop** · **GitHub CLI (`gh`)**

### Quick start

```bash
git clone https://github.com/psyphon1/Meridian.git
cd Meridian

# 1. Configure environment (12-factor: config lives in env, never in code)
cp .env.example .env          # fill in the GitHub App / OAuth / KMS values

# 2. Start backing services — works today
docker compose up -d postgres redis

# 3. Install Python + frontend dependencies
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pnpm install

# 4. Run the test suite (smoke tests currently passing)
pytest
```

Full developer setup — credentials (GitHub App / OAuth / KMS), webhook forwarding via `gh webhook forward`, and troubleshooting — is in [`docs/SETUP.md`](docs/SETUP.md). Developer task targets (`make lint`, `make typecheck`, `make test`, `make dev`) are defined in the root [`Makefile`](Makefile).

## Documentation

Full index: [`docs/README.md`](docs/README.md).

| Document | What it covers |
|---|---|
| [Product Requirements (PRD)](docs/PRD.md) | Problem, goals, users, functional requirements, success metrics, release criteria |
| [System Design (SDD)](docs/SDD.md) | Architecture, pipeline, evidence gate, data design, queues, failure handling |
| [Technical Requirements (TRD)](docs/TRD.md) | Tech stack, SLAs/SLOs, security requirements, quality gates, phase plan |
| [Architecture](docs/ARCHITECTURE.md) | C4 views, key decisions, webhook ingestion + GitHub credential lifecycle |
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Monorepo layout, boundaries, dependency rules |
| [Security](docs/SECURITY.md) | Boundary model, secrets/KMS, sandbox posture, OWASP ASVS + LLM Top 10 mapping |
| [Compliance](docs/COMPLIANCE.md) | Hash-chained audit log, retention/deletion, redaction |
| [Observability](docs/OBSERVABILITY.md) | Golden signals, alerting policy, tracing, logging, dashboards |
| [Deployment](docs/DEPLOYMENT.md) | Environments, build pipeline, blue-green rollout, runtime topology |
| [Setup](docs/SETUP.md) | Local development, credentials, daily workflow, troubleshooting |
| [Code Standards](docs/CODE_STANDARDS.md) | Python/TypeScript style, tooling, quality rules |
| [Developer Standards](docs/DEVELOPER_STANDARDS.md) | Workflow: issues, PRs, tests, ADRs, Definition of Done |
| [Agent Standards](docs/AGENT_STANDARDS.md) | AI-agent behavioral and safety rules |
| [Beginner's Guide](docs/BEGINNERS_GUIDE.md) | Plain-English overview (no prerequisites) |
| [Learning Guide](docs/LEARNING_GUIDE.md) | Full curriculum: 51 sections across tech stack, system design, and scaling |
| [Architecture Decision Records](docs/adr/README.md) | ADR-001…005 + process (MADR format) |

> **AI coding agents:** start with [`AGENTS.md`](AGENTS.md) — the mandatory entry point defining the reading order (design artifacts in `docs/design/` first, then `docs/CODE_STANDARDS.md` and `docs/DEVELOPER_STANDARDS.md`, always).

## Architecture decisions

| ADR | Decision |
|---|---|
| [ADR-001](docs/adr/adr-001-github-app.md) | GitHub App (installation-scoped) over personal access tokens |
| [ADR-002](docs/adr/adr-002-postgres-pgvector.md) | PostgreSQL + pgvector first; Qdrant only on a metric trigger |
| [ADR-003](docs/adr/adr-003-hybrid-retrieval.md) | Code graph + hybrid retrieval over embeddings alone |
| [ADR-004](docs/adr/adr-004-evidence-gate.md) | Evidence gate for high-severity findings (schema-enforced) |
| [ADR-005](docs/adr/adr-005-human-escalation.md) | Human escalation for high-impact / ambiguous decisions |

Architecture changes require an ADR before implementation ([`docs/adr/`](docs/adr/README.md), MADR format).

## Status & roadmap

🚧 **Pre-Alpha — design complete, build starting.** Full project history in [`track.md`](track.md).

**Done:** complete documentation set (PRD/SDD/TRD/architecture/security/compliance/observability/deployment) · modular monorepo scaffold (54+ directories) · build config filled (`pyproject.toml`, `package.json`, `docker-compose.yml`, `Makefile`) · CI pipeline (lint → typecheck → test → secret scan → SAST → SBOM) · GitHub hygiene (CODEOWNERS, issue/PR templates, Dependabot) · bootstrap script + smoke tests (passing) · 5 ADRs · beginner + learning guides.

**Build order** (from [`docs/TRD.md`](docs/TRD.md)):

| Phase | Scope | Status |
|---|---|---|
| P1 | GitHub App + FastAPI + PostgreSQL + Redis | Next up |
| P2 | LangGraph workflow + basic LLM review | Planned |
| P3 | Tree-sitter + SCIP/LSP + repository indexing | Planned |
| P4 | Hybrid retrieval + historical context | Planned |
| P5 | Specialized agents + risk-based routing | Planned |
| P6 | Semgrep + CodeQL + sandbox verification | Planned |
| P7 | Evidence gate + citations + human escalation | Planned |
| P8 | Observability + audit log + cost controls | Planned |
| P9 | Production hardening + benchmark suite | Planned |

## Success metrics (V1)

| Metric | Target |
|---|---|
| Median time-to-first-useful-review | < 3 min |
| False-positive rate | < 15% |
| Human acceptance rate | > 70% |
| Escalation rate | 5–15% |
| Citation verifiability (BLOCKING/HIGH) | 100% |
| Cost per PR | < $0.50 median (BYOK spend) |
| Onboarding completion | > 80% |

## Security

- **BYOK + envelope encryption** — user LLM keys are wrapped with a KMS/Vault key-encryption key; only ciphertext is persisted; decryption happens in-memory in the isolated worker and is zeroized after.
- **Prompt-injection defense** — repository content and PR text are untrusted data, never instructions; the trust hierarchy is enforced at the system/developer-message level.
- **Sandbox isolation** — deny-all egress, command allowlists, resource limits, ephemeral per-job runtime.
- **Standards alignment** — OWASP ASVS v5 (targeting Level 2 for auth/key/webhook flows) and the OWASP Top 10 for LLM Applications, each mapped to a concrete Meridian control.

See [`docs/SECURITY.md`](docs/SECURITY.md) and [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) for the full control set.

**Report vulnerabilities privately** via a GitHub security advisory on `psyphon1/Meridian` — do not open a public issue.

## Contributing

Contributions are welcome. Please follow the repository conventions:

- **Conventional Commits** only; keep PRs small and reviewable (see the [PR template](.github/pull_request_template.md)).
- Python: **Ruff** + **mypy strict** + **pytest** · TypeScript: **strict** + **ESLint** + **Prettier** ([`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md)).
- Behavior changes include tests; observability is part of the Definition of Done ([`docs/DEVELOPER_STANDARDS.md`](docs/DEVELOPER_STANDARDS.md)).
- Architecture changes require an ADR first; no credential ever enters source, images, or logs.
- **AI coding agents** must read [`AGENTS.md`](AGENTS.md) before touching any file.

## License

[MIT](LICENSE) © Chinmay Duse

---

**Meridian — Autonomous AI PR Reviewer.** *Your autonomous first-pass senior engineer for every GitHub pull request.*
