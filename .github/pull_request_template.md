# Meridian Pull Request

## Summary

<!-- What does this PR change and why? Link the issue / ADR if applicable. -->

## Type

- [ ] Feature · [ ] Bug fix · [ ] Refactor · [ ] Docs · [ ] Infra/CI · [ ] Tests

## Checklist (required)

- [ ] Conventional Commits title (e.g. `feat(api): ...`)
- [ ] Tests added/updated for all critical behavior (PROJECT_STRUCTURE.md rule 8)
- [ ] No secrets, tokens, or repository content in logs, traces, or fixtures
- [ ] No direct LLM calls outside the model gateway; no raw GitHub API calls outside the GitHub adapter
- [ ] DB schema changes go through `db/migrations/` (expand-first, backward compatible)
- [ ] Architecture changes: ADR proposed under `docs/adr/` and linked
- [ ] Prompts changed? Versioned under `prompts/` + eval cases updated in `evals/`
- [ ] `ruff` / `mypy` / `tsc --strict` clean; docs updated if user-facing behavior changed

## Reviewer Notes

<!-- Anything reviewers should focus on. If this PR adds/changes an agent behavior, link the eval report. -->
