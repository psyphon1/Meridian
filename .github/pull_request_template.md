# Meridian Pull Request

## What

<!-- One or two sentences: exactly what this PR changes. List files/packages touched. No "why" here. -->

## Why

<!-- The motivation: which problem, issue, ADR, or plan task this solves. Link the issue / ADR / implementation plan if applicable. -->

## When

<!-- Timeline context: e.g. which milestone/phase this lands, target release/tag, or merge order for stacked PRs (base PR must merge first). -->

## How

<!-- The approach: key design decisions, patterns used, and how it was verified (commands run, test counts). Cite files, commits, tests, and docs. -->

## Impact

<!-- Who/what is affected: services, schemas, APIs, docs, CI. Note anything NOT affected. -->

## Rollback

<!-- How to revert safely: single revert commit? migration downgrade needed? feature flag? -->

## Type

- [ ] Feature · [ ] Bug fix · [ ] Refactor · [ ] Docs · [ ] Infra/CI · [ ] Tests

## Checklist (required)

- [ ] Conventional Commits title (e.g. `feat(api): ...`)
- [ ] Tests added/updated for all critical behavior (PROJECT_STRUCTURE.md rule 8)
- [ ] **Unit and integration tests pass locally** (`make test-unit && make test-integration` or equivalent)
- [ ] No secrets, tokens, repository content in logs, traces, or fixtures
- [ ] **No `.env` files, environment variables, or hardcoded secrets in any committed file** (verified by `gitleaks` + manual review)
- [ ] All claims in PR description are **citation-based** (link code, tests, ADRs, or design docs)
- [ ] No false claims — every stated behavior is demonstrable by a test or referenced document
- [ ] No direct LLM calls outside the model gateway; no raw GitHub API calls outside the GitHub adapter
- [ ] DB schema changes go through `db/migrations/` (expand-first, backward compatible)
- [ ] Architecture changes: ADR proposed under `docs/adr/` and linked
- [ ] Prompts changed? Versioned under `prompts/` + eval cases updated in `evals/`
- [ ] `ruff` / `mypy` / `tsc --strict` clean; docs updated if user-facing behavior changed
- [ ] **Design doc / spec metadata header present** (`Created:`, `Author:`, `Version:`, `Status:`) if this PR introduces or modifies a design doc

## Reviewer Notes

<!-- Anything reviewers should focus on. If this PR adds/changes an agent behavior, link the eval report. -->
