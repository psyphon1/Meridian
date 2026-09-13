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
- **All claims in a PR description must be citation-based.** Every behavioral claim, performance claim, or architectural justification must reference: (a) a code location, (b) a test result output, (c) a design doc section, (d) an ADR, or (e) a reproducible benchmark run. **False claims are unacceptable** — if a claim cannot be verified by a reviewer reading the PR, it must not be made.
- **Use the PR template.** Every PR must fill the `.github/pull_request_template.md` checklist completely. Unchecked items must be explicitly justified in the PR body.

## 4. Testing standards

| Quadrant | Scope | Runs |
|---|---|---|
| Unit | Pure logic, no I/O, no network | Always, fast (< 60 s) |
| Integration | Backing services (Postgres/Redis) via docker-compose, adapters | CI (services up) |
| Security | Evidence gate, sandbox isolation, injection defenses | CI |
| E2E | Full webhook → review pipeline | CI / staging gate |

See `docs/CODE_STANDARDS.md` §6 and `make test*` targets.

### 4.1 Pre-commit testing gate

**Unit and integration tests must pass before any commit reaches the remote.** This is enforced by:
- **Pre-commit hook** (`.pre-commit-config.yaml`): runs unit tests (`pytest tests/unit -q`) + gitleaks + ruff + mypy.
- **Pre-push hook** (`.husky/pre-push` or `pre-commit` pre-push stage): runs integration tests (`pytest tests/integration -q`) + e2e smoke if applicable.
- **CI enforcement**: the same test matrix runs again in GitHub Actions; no merge with failing CI.

No commit may bypass these hooks via `--no-verify` without explicit written justification in the commit message (e.g., `[skip-hooks] WIP: ...`). Such commits must be amended before PR.

## 5. What we never do

- No credentials in source, images, config committed to the repo, or logs — **ever** (12-factor + `docs/SECURITY.md`).
- No environment variables, `.env` files, or secrets of any kind committed to the repository — **ever**. This includes "example" files that contain real-looking values, test fixtures with hardcoded tokens, or documentation snippets with live credentials.
- No merging with failing CI or without `CODEOWNERS` approval.
- No force-pushing to `main`; no rewriting shared history.
- No bypassing the evidence gate for BLOCKING/HIGH findings (ADR-004) — in product code or review agents.

## 6. Document metadata (design docs, specs, plans)

Every design document, specification, or plan file under `docs/` must begin with a metadata header:

```markdown
---
Created: YYYY-MM-DD
Author: <name>
Version: <semver or draft number>
Last Updated: YYYY-MM-DD
Status: draft | review | accepted | superseded
---
```

- **Created**: date the document was first authored (not the date of last edit).
- **Author**: individual or team responsible for the document.
- **Version**: semantic version of the document (not the product). Major version bumps when sections are removed or decisions reversed; minor for additions; patch for clarifications.
- **Last Updated**: date of the most recent material change.
- **Status**: `draft` (work in progress), `review` (under team review), `accepted` (authoritative), `superseded` (replaced by a newer doc; link the successor).

**Rationale:** The codebase is long-lived and agent-maintained. Without creation dates and version metadata, it is impossible to know whether a document reflects current thinking or historical context. Agents must not work from stale specs.

## 7. Pre-commit toolchain

### 7.1 Required tools

| Tool | Purpose | Installation |
|---|---|---|
| **pre-commit** (Python) | Git hook framework — runs all checks | `pip install pre-commit` (already in `[dev]`) |
| **gitleaks** | Secret scanning — prevents credential commits | Via pre-commit hook (auto-installed) or `brew install gitleaks` / `choco install gitleaks` |
| **husky** (Node) | Git hook framework for frontend/TypeScript checks | `pnpm install` (already in root dev deps) |
| **lint-staged** | Run linters only on staged files | `pnpm install` (already in root dev deps) |

### 7.2 Hook stages

| Stage | Runs | When |
|---|---|---|
| `pre-commit` | gitleaks (secrets) · ruff (lint+format) · mypy · pytest unit tests · `.env` file scanner | Every `git commit` |
| `pre-push` | pytest integration tests · pnpm lint · pnpm typecheck | Every `git push` |

### 7.3 Setup (one-time per clone)

```powershell
# After `make setup` or `pnpm install` + `pip install -e ".[dev]"`
pre-commit install --install-hooks
pnpm exec husky install
```

### 7.4 Skipping hooks (emergency only)

`git commit --no-verify` is prohibited for production-bound commits. It is acceptable only for:
- WIP commits on private branches that will be squashed/amended before PR.
- Explicitly documented emergencies with a `[skip-hooks]` tag in the commit message.

Any commit that bypasses hooks must be re-checked manually (`make lint && make test && make typecheck`) before PR.
