# Meridian — Architecture Decision Records

ADRs capture each architecturally significant decision and its rationale. We use the **MADR** format (Nygard's template extended with decision drivers, options, and outcomes), per adr.github.io practice. The collection of ADRs is the project's decision log — read it to learn *why* the system is the way it is, not just what it is.

## Process

1. Copy `adr/template.md` → `adr-NNN-title-kebab-case.md` (next number, zero-padded).
2. Status `Proposed` while discussed; `Accepted` when the decision is made; `Superseded by ADR-XXX` (never delete).
3. Decisions are **immutable once accepted** — supersede, don't edit history.
4. Per PROJECT_STRUCTURE.md rule 9: any architecture change **requires** an ADR before implementation.
5. Keep each ADR about **one** decision. Link related ADRs and code/docs.

## Index

| ADR | Title | Status |
|---|---|---|
| [ADR-001](adr-001-github-app.md) | GitHub App (installation-scoped) over personal access tokens | Accepted |
| [ADR-002](adr-002-postgres-pgvector.md) | PostgreSQL + pgvector first; Qdrant only on metric trigger | Accepted |
| [ADR-003](adr-003-hybrid-retrieval.md) | Code graph + hybrid retrieval over embeddings alone | Accepted |
| [ADR-004](adr-004-evidence-gate.md) | Schema-enforced evidence gate for high-severity findings | Accepted |
| [ADR-005](adr-005-human-escalation.md) | Human escalation for high-impact decisions | Accepted |
| [ADR-006](adr-006-phase1-github-app-webhook-ingestion.md) | Phase 1 — GitHub App + webhook ingestion layer (outbox, priority streams, schema, adapter, worker, error envelope, trace propagation) | Accepted |
