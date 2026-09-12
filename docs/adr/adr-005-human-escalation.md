# ADR-005 — Human escalation for high-impact decisions

**Status:** Accepted · **Date:** 2026-09-12

## Context

An autonomous reviewer will encounter PRs (auth changes, migrations, ambiguous architecture impact) where being wrong is expensive and evidence tooling cannot fully adjudicate. OWASP LLM08 (excessive agency) and LLM09 (overreliance) frame the failure mode.

## Decision Drivers

- Humans remain the final merge authority — non-negotiable product boundary (v2 spec)
- Escalation must itself be a defined, auditable pipeline outcome — not a failure
- Trust erosion asymmetry: one confident wrong BLOCKING costs more than ten honest escalations

## Considered Options

1. **Always decide, publish confidence scores** — pushes judgment burden onto readers; overconfident output at the edges.
2. **Never publish on uncertainty, stay silent** — silent drops violate the core reliability promise.
3. **Explicit escalation outcome** — visible, auditable handoff to a human with the full evidence trail.

## Decision

**Escalation is a first-class pipeline terminal state** (`ESCALATED`), used when risk tier is critical, evidence is incomplete for a high-impact claim, or repo policy demands sign-off. Escalations carry the same SHA-pinned evidence trail as published findings. Adjudicator thresholds for escalation are per-repo configurable (risk policy).

## Consequences

- Positive: bounded blast radius for autonomy; consistent product behavior at uncertainty; escalation rate is a monitored SLO input.
- Negative: escalation fatigue is possible — mitigated by measuring escalation rate and precision (OBSERVABILITY.md §5) and letting repo policy tune thresholds.
