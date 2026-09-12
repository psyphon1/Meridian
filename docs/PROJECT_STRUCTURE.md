# Meridian — Project Structure

**Full document:** [`Meridian_PROJECT_STRUCTURE.md`](design/Meridian_PROJECT_STRUCTURE.md)

## Layout (modular monorepo)

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
├── docs/            # This documentation set + adr/
├── prompts/         # system, review, evidence, adjudication (version-controlled)
├── evals/           # datasets, cases, graders, regression, reports
├── tests/           # unit, integration, security, e2e, fixtures
├── scripts/         # bootstrap, indexing, evaluation, migrations, development
└── .github/         # workflows, ISSUE_TEMPLATE, PR template, dependabot
```

## Dependency Rules

**Allowed:** apps → packages · services → packages · packages → lower-level packages · infra → deployment definitions.
**Forbidden:** package → another package's internals · agent → database internals · agent → GitHub SDK directly. Use interfaces/adapters.

## Project-Level Rules

1. No business logic in controllers/routes.
2. No direct LLM calls without the model gateway.
3. No raw GitHub API calls outside the GitHub adapter.
4. No direct Docker/Firecracker calls outside the sandbox package.
5. No finding bypasses the evidence/adjudication pipeline.
6. No secret in logs or traces.
7. All external/model-facing schemas are versioned.
8. All critical behavior has automated tests.
9. Architecture changes require an ADR.
10. New agents require evaluation cases before production use.

## Guiding principle

The repository structure should make the architecture obvious — if locating the API, workflow, agents, retrieval, or verification requires reading unrelated code, the structure is wrong.
