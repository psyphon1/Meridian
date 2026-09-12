# Meridian — Autonomous AI PR Reviewer
# Documentation Index

| Document | Purpose |
|---|---|
| [PRD.md](PRD.md) | Product Requirements — problem, goals, users, user stories, acceptance criteria |
| [SDD.md](SDD.md) | System Design — architecture, components, interfaces, data design |
| [TRD.md](TRD.md) | Technical Requirements — tech stack, SLAs, quality gates, DoD |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture views and decisions |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Monorepo layout, boundaries, dependency rules |
| [SECURITY.md](SECURITY.md) | Security policy and controls |
| [COMPLIANCE.md](COMPLIANCE.md) | Audit, retention, deletion, compliance baseline |
| [CODE_STANDARDS.md](CODE_STANDARDS.md) | Code style and quality standards |
| [DEVELOPER_STANDARDS.md](DEVELOPER_STANDARDS.md) | Engineering workflow standards |
| [AGENT_STANDARDS.md](AGENT_STANDARDS.md) | AI agent behavioral and safety standards |
| [UI_UX.md](UI_UX.md) | Dashboard UI/UX guidelines |
| [SETUP.md](SETUP.md) | Local development setup |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deployment architecture, environments, rollout strategy |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Golden signals, metrics, tracing, logging, alerting |
| [adr/](adr/) | Architecture Decision Records (ADR-001…005 + process) |
| [`../AGENTS.md`](../AGENTS.md) | **Mandatory entry point for all AI coding agents** — reading order, hard rules, conflict precedence |

## Full source documents (`docs/design/`)

The complete, authoritative design artifacts live in [`docs/design/`](design/):

- [`Meridian_Full_Session_Context.md`](design/Meridian_Full_Session_Context.md) — full session context / agent handoff (authoritative)
- [`Meridian_Design_Doc_Final.html`](design/Meridian_Design_Doc_Final.html) — master design doc (includes the complete v2 spec as appendix — **source of truth when conflicts arise**)
- [`Meridian_SDD.md`](design/Meridian_SDD.md), [`Meridian_TRD.md`](design/Meridian_TRD.md), [`Meridian_Architecture.md`](design/Meridian_Architecture.md), [`Meridian_PROJECT_STRUCTURE.md`](design/Meridian_PROJECT_STRUCTURE.md)

The files under `docs/` are the working, industry-structured versions; where they summarize, the `docs/design/` documents are authoritative.

### Single source of truth

There are deliberately two documentation layers, and they are **not** a duplication to be reconciled file-by-file:

- **`docs/design/`** is the *authoritative source of truth* — especially [`Meridian_Design_Doc_Final.html`](design/Meridian_Design_Doc_Final.html) (complete v2 spec in its appendix) and [`Meridian_Full_Session_Context.md`](design/Meridian_Full_Session_Context.md). When any two documents disagree, the design doc wins.
- **`docs/`** is the *working layer* — industry-structured PRD/SDD/TRD/standards docs that are faster to read and edit day-to-day.

**Rule:** if a change alters a requirement, contract, or architecture decision, update *both* layers (or log an ADR when it's an architecture change). If they ever drift, trust `docs/design/` over `docs/`.
