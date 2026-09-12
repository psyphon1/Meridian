# Meridian — UI / UX Guidelines

**Per design doc §31 / v2 spec §5.**

## Primary dashboard sections

Overview · Repositories · Review Runs · Findings · Rules · Spend · Audit · Settings.

Key surfaces:

- Empty state → "Connect a repository" (GitHub App install flow) → BYOK setup (blocking gate).
- **Live review status** in real time: `QUEUED → CONTEXT_BUILDING → ANALYZING → VERIFYING → PUBLISHING` (including `QUEUED_NO_KEY`, `PARTIAL_REVIEW`, `ESCALATED`, `FAILED`).
- Token/cost meter updating in real time; per-PR and per-day spend.
- Escalation queue for human-judgment cases.

## Review detail view

Summary · risk · duration · files analyzed · findings · evidence · verification method · concise rationale · recommendation · operational (not hidden-CoT) trace.

## Hard UX rule

> The user can answer **"Why did Meridian comment?"** in under 30 seconds.

Never expose chain-of-thought. Expose evidence, source, verification, and recommendation. Failed analyses are visible on the dashboard — never silent.
