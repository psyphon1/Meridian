# ADR-001 — GitHub App (installation-scoped) over personal access tokens

**Status:** Accepted · **Date:** 2026-09-12

## Context

Meridian must access tenant repositories, receive webhooks, and publish reviews. Options: personal access tokens (PAT), OAuth app, or GitHub App.

## Decision Drivers

- Multi-tenant by design (tenant = user) → access must be scoped per installation, not per person
- Tight rate limits (5,000 req/hr with installation tokens) vs PAT's lower shared limits
- Webhook secret + HMAC verification mandatory for untrusted input
- Fine-grained, minimal permissions with per-install approval; auditability of installs
- GitHub's published best practices: minimum permissions, minimum webhooks, token caching/expiry

## Considered Options

1. **PATs** — trivially simple but tied to personal accounts, coarse scopes, no per-repo install lifecycle, unclear revocation story for tenants.
2. **OAuth app** — user-delegated, but no install lifecycle, broader scopes, weaker webhook story.
3. **GitHub App** — installation-scoped, fine-grained permissions, its own rate limit, first-class webhooks, uninstall events drive data deletion.

## Decision

Use a **GitHub App**. Identity for dashboard sign-in is a separate GitHub OAuth App (session only). App credentials follow GitHub's guidance: minimum permissions, subscribe to the minimum event set (`pull_request`, `installation`, `installation_repositories`), webhook secret with HMAC verification, short-lived installation tokens cached per installation, `Retry-After` honored for secondary rate limits.

## Consequences

- Positive: clean tenant scoping; revocable, auditable access; uninstall → cascading deletion (COMPLIANCE.md); higher rate limits.
- Negative: credential lifecycle complexity (JWT → installation token exchange, key rotation, breach playbook in SECURITY.md §5); users must re-approve permission changes (App must be backwards-compatible and listen for `new_permissions_accepted`).
