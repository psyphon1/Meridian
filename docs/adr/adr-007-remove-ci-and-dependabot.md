# ADR-007: Remove GitHub Actions CI and Dependabot

- **Status:** Accepted
- **Date:** 2026-10-13
- **Deciders:** Chinmay Duse (owner)

## Context

The repository had `.github/workflows/ci.yml` (lint, typecheck, test, secret scan, SAST, SBOM) and `.github/dependabot.yml`. Dependabot opened many PRs (13 open at decision time) and sent a high volume of notification emails. CI failures added more. The owner is the only maintainer and does not want the notification load.

`docs/design/*` (TRD §29, SDD, Architecture) list GitHub Actions CI/CD. This ADR deviates from those documents on purpose. The design documents are left unchanged as the historical record.

## Decision

- Delete `.github/workflows/ci.yml` and `.github/dependabot.yml`.
- Close open Dependabot PRs and delete their branches.
- Disable Dependabot alerts and security updates for the repository.
- Run checks locally: `make lint`, `make typecheck`, `make test`.

## Consequences

- No automated merge gate. Local checks are the only gate; PR authors must run them and report real results.
- Secret scan, SAST (CodeQL/Semgrep) and SBOM are no longer automated. Run them manually before a release.
- No automated dependency or vulnerability updates. Review dependencies manually.
- Reversible: restore the two files from git history (commit before this ADR) and re-enable Dependabot in repository settings.
- Production hardening (Phase 9) must re-evaluate release-time security scanning.
