# ADR-004 — Schema-enforced evidence gate for high-severity findings

**Status:** Accepted · **Date:** 2026-09-12

## Context

The core product risk is hallucinated findings destroying trust. Prompt-level ("please cite sources") instructions are not enforceable; severity BLOCKING/HIGH must be *provably* grounded.

## Decision Drivers

- User story US-06: serious findings must be reproduced before they block a PR
- Trust model: the LLM is one reasoning component, never the source of truth
- Every published comment must carry a SHA-pinned permalink that resolves

## Considered Options

1. **Prompt-only citation** — unenforceable, degrades silently under context pressure.
2. **Post-hoc lint of LLM output** — checks format, not truth; a fabricated-but-well-formed citation passes.
3. **Schema + adjudicator re-derivation gate** — the pipeline rejects ungrounded high-severity claims mechanically.

## Decision

**Enforce the gate in the pipeline, in schema, and in the adjudicator:**

- `IF severity ∈ (BLOCKING, HIGH)`: `evidence_ref` **must** be non-null and of type `tool_run | test_execution | sha_pinned_code_span`; the adjudicator must **re-derive** the claim from the artifact — failure downgrades to INFO or suppresses.
- Evidence is produced by deterministic verifiers (Semgrep, CodeQL, sandbox, tests) that agents invoke but cannot override.
- Published comments embed `github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}`.

## Consequences

- Positive: verifiable-by-construction findings; citation-verifiable rate measurable at 100% target; reviewers can re-derive any claim.
- Negative: some true findings get downgraded when evidence tooling can't reach them — an accepted precision/recall tradeoff; mitigation is broadening evidence tools over time, not weakening the gate.
