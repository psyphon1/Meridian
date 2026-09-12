# Meridian — Autonomous AI PR Reviewer
# Developer Standards

**Per v2 spec / design doc §42.**

> **AI agents:** [`AGENTS.md`](../AGENTS.md) is the mandatory entry point for any agent working in this repo — these developer standards apply to agent work exactly as to human work, without exception.

## 1. Workflow (every change)

1. **Every feature begins with an issue** (`.github/ISSUE_TEMPLATE/`) that states the problem, the proposed behavior, and **written acceptance criteria** (Gherkin `Given/When/Then` preferred).
2. **Architecture changes require an ADR first** (MADR format, `docs/adr/`, template provided). No ADR → no architecture change.
3. **Branch off `main`**; short-lived branches. Conventional Commit messages; a PR may contain multiple commits but one logical change.
4. **PR must reference its issue** and pass the checklist in `.github/pull_request_template.md` before requesting review.

## 2. Definition of Done

A change is **not done** until all of these hold:

- [ ] Acceptance criteria are met and demonstrated by tests.
- [ ] Behavior changes include tests (unit + integration per code layer); production bugs get regression tests.
- [ ] All lint + typecheck + tests pass in CI (Ruff, mypy, ESLint/tsc, pytest).
- [ ] **Observability is in place** — traces, metrics, and structured logs exist for the new behavior (see `docs/OBSERVABILITY.md`). A feature without traces/metrics is incomplete.
- [ ] Security-sensitive paths pass the ASVS checklist (`docs/SECURITY.md`) and contain no credentials in source/logs/traces.
- [ ] Docs updated if the change alters contracts, env vars, or architecture (this is why `track.md` and design docs stay current).
- [ ] No placeholders, `TODO`s, or stubbed branches shipping as "done" (see AGENTS.md rule "placeholders are not deliverables").

## 3. PR discipline

- **Reviewable size.** Split oversized changes: prefer ≤ 400 changed lines for a single PR; anything larger must justify itself or be split.
- **Every PR is a coherent unit** — reviewers can summarize its intent in one sentence.
- **Evidence over opinion in review**, same standard Meridian enforces on the PRs it reviews: findings cite code locations or reproducible evidence, not vibes.

## 4. Testing standards

| Quadrant | Scope | Runs |
|---|---|---|
| Unit | Pure logic, no I/O, no network | Always, fast (< 60 s) |
| Integration | Backing services (Postgres/Redis) via docker-compose, adapters | CI (services up) |
| Security | Evidence gate, sandbox isolation, injection defenses | CI |
| E2E | Full webhook → review pipeline | CI / staging gate |

See `docs/CODE_STANDARDS.md` §6 and `make test*` targets.

## 5. What we never do

- No credentials in source, images, config committed to the repo, or logs — **ever** (12-factor + `docs/SECURITY.md`).
- No merging with failing CI or without `CODEOWNERS` approval.
- No force-pushing to `main`; no rewriting shared history.
- No bypassing the evidence gate for BLOCKING/HIGH findings (ADR-004) — in product code or review agents.
