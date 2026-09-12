# Meridian — Developer Standards

**Per v2 spec / design doc §42.**

- Every feature begins with an issue + acceptance criteria.
- PRs remain reviewable — split oversized changes.
- Behavior changes include tests.
- **Architecture changes require an ADR** (see [adr/](adr/README.md)).
- Production bugs get regression tests where practical.
- **Observability is part of Definition of Done** — a feature without traces/metrics is incomplete.
- No credentials in source, images, or logs — ever.

## Review culture

Meridian itself enforces "evidence over opinion" for PRs it reviews; human reviewers on this repo apply the same standard: findings should cite code locations or reproducible evidence.
